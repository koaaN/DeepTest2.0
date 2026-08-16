/*
 * Modified for DeepTest 2.0: project-ID-specific OnePlus kernel entries.
 * See the repository THIRD_PARTY_NOTICES.md and Apache-2.0 LICENSE.
 * 6.12.38-android16-5-g844001fb8721-ab14552068-4k
 */

OFFSETS_ENTRY(
    "6.12.38-android16-5-g844001fb8721-ab14552068-4k",
    .prjid = "25821", /* OnePlus 15T */
    STRUCT_OFFSETS_6_12,
    .pselect_waiter_shift = 0,
    .off_init_task = 0x0240cf00,
    .off_init_cred = 0x02422c70,
    .off_root_task_group = 0x0263d580,
    .off_selinux_enforcing = 0x026894d0,
    .off_selinux_blob_sizes = 0x018494e8,
    .off_security_hook_heads = 0x00000000,
    .off_slide_nfulnl_logger = 0x024021a0,
    .off_slide_boot_id = 0x026aa868,
    .off_slide_loggers_0_1 = 0x024020e8,
),

OFFSETS_ENTRY(
    "6.12.38-android16-5-g844001fb8721-ab14552068-4k",
    .prjid = "24855", /* OnePlus Ace 6T PLR110_16.0.8.301 */
    STRUCT_OFFSETS_6_12_A800,
    .pselect_waiter_shift = 0,
    .off_init_task = 0x0240cf00,
    .off_init_cred = 0x02422c70,
    .off_root_task_group = 0x0263d580,
    .off_selinux_enforcing = 0x026894d0,
    .off_selinux_blob_sizes = 0x018494e8,
    .off_security_hook_heads = 0x00000000,
    .off_slide_nfulnl_logger = 0x024021a0,
    .off_slide_boot_id = 0x026aa868,
    .off_slide_loggers_0_1 = 0x024020f0,
),

/* BTF reference (runtime uses target.h defaults): */
/* #define STRUCT_PAGE_SIZE 0x40 */
/* #define STRUCT_PAGE_COMPOUND_HEAD 0x8 */
/* #define STRUCT_PAGE_TYPE 0x30 */
/* #define STRUCT_SLAB_CACHE 0x8 */
/* #define STRUCT_MM_STRUCT 0x4C0 */
