package com.koaan.deeptest2;

import android.annotation.SuppressLint;
import android.os.Bundle;
import android.graphics.Color;
import android.content.Intent;
import android.net.Uri;
import java.nio.file.StandardCopyOption;
import android.webkit.JavascriptInterface;
import android.webkit.JsPromptResult;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebViewClient;
import android.webkit.WebView;
import androidx.appcompat.app.AppCompatActivity;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {
    private WebView web;
    private final java.util.concurrent.ExecutorService worker = Executors.newSingleThreadExecutor();
    private static final int PICK_AUTH = 4102;
    private static final int PICK_PROFILE = 4103;
    private static final int EXPORT_JSON = 4104;
    private String exportPayload;

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
        web = new WebView(this);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onJsPrompt(WebView view, String url, String message, String defaultValue, JsPromptResult result) {
                view.evaluateJavascript("window.onNativeCaptchaPrompt&&window.onNativeCaptchaPrompt(" + JSONObject.quote(message) + ")", null);
                result.confirm("");
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    return true;
                }
                return false;
            }
            @Override public void onPageFinished(WebView view, String url) {
                view.evaluateJavascript("(()=>{const n=[['◉','Account'],['⌁','Request'],['♜','Root'],['▣','Install'],['⚙','Settings']];document.querySelectorAll('.nav button').forEach((b,i)=>{b.textContent=n[i][0];b.title=n[i][1]});const s=document.createElement('style');s.textContent='.nav button{min-height:54px;min-width:58px;font-size:25px!important;padding:13px 18px!important}.nav button.on{background:#2b234f;border-radius:14px}.request-done{display:none;box-sizing:border-box;border:1px solid #269c73;background:#103a2d;color:#53e0a9;border-radius:14px;padding:17px;margin-bottom:14px;font-size:16px;font-weight:800}.request-done.show{display:block}';document.head.appendChild(s);const r=document.getElementById('request');if(r&&!document.getElementById('requestDone')){const b=document.createElement('div');b.id='requestDone';b.className='request-done';r.insertBefore(b,r.firstElementChild)}const old=window.render;window.render=function(id,v){old(id,v);if(id==='requestOut'){try{const x=JSON.parse(v),b=document.getElementById('requestDone');if(b&&x.ok){b.className='request-done show';b.textContent=x.unlockCode?'✓ Unlock code received — request complete':'✓ Request complete'}}catch(e){}}}})()", null);
                view.evaluateJavascript("(()=>{const n=[\"<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='8' r='3.2' fill='none' stroke='currentColor' stroke-width='1.8'/><path d='M5.5 20c.7-3.2 2.9-5 6.5-5s5.8 1.8 6.5 5' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round'/></svg>\",\"<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M5 5.5h14v13H5z' fill='none' stroke='currentColor' stroke-width='1.8'/><path d='m8 10 1.8 1.8L13 8.5M8 15h7' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/></svg>\",\"<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M12 3 19 6v5c0 4.4-2.9 7.5-7 10-4.1-2.5-7-5.6-7-10V6z' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linejoin='round'/><path d='m9 12 2 2 4-4' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/></svg>\",\"<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M5 4.5h14v15H5z' fill='none' stroke='currentColor' stroke-width='1.8'/><path d='M12 8v8m0 0-3-3m3 3 3-3' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/></svg>\"];document.querySelectorAll('.nav button').forEach((b,i)=>{b.innerHTML=n[i];b.setAttribute('aria-label',['Account','Request','Root','Install'][i]);const s=b.querySelector('svg');if(s){s.style.width='28px';s.style.height='28px';s.style.display='block'}})})()", null);
                view.evaluateJavascript("(()=>{const s=document.createElement('style');s.textContent='body.bright{--bg:#f4f6fb;--card:#fff;--line:#d5dbea;--text:#182033;--muted:#5d6880}body.bright .top,body.bright .nav{background:#fff}body.bright input,body.bright select,body.bright textarea{background:#f0f2f7;color:#182033}body.bright .nav button{color:#1f1f1f!important}.nav button{background:transparent!important}.nav button.on{background:#2b234f!important;color:#fff!important}body.bright .nav button.on{background:#ddd6ff!important;color:#4c3cc4!important}body.bright .dt-loading{background:#fff;color:#182033;border-color:#b8adff;box-shadow:0 10px 35px #77809955}body.bright .request-done{background:#dff8ed;color:#13714f;border-color:#58b894}body.bright .root-done.ok{background:#dff8ed;color:#13714f;border-color:#58b894}body.bright .root-done.bad{background:#ffe5ea;color:#a52d45;border-color:#dc7288}body.bright button{background:#e2e6f0;color:#182033}body.bright button.primary{background:var(--purple);color:#fff}body.bright .result{background:#eef0f5;color:#273047}body.bright .ok{color:var(--green)!important}body.bright .settings-row{background:#fff;color:#182033}body.bright button:active{background:#cbd2e1!important;filter:none!important}';document.head.appendChild(s);const b=document.querySelectorAll('.nav button')[4];if(b){b.innerHTML=\"<svg viewBox='0 -960 960 960' aria-hidden='true'><path d='M433-80q-27 0-46.5-18T363-142l-9-66q-13-5-24.5-12T307-235l-62 26q-25 11-50 2t-39-32l-47-82q-14-23-8-49t27-43l53-40q-1-7-1-13.5v-27q0-6.5 1-13.5l-53-40q-21-17-27-43t8-49l47-82q14-23 39-32t50 2l62 26q11-8 23-15t24-12l9-66q4-26 23.5-44t46.5-18h94q27 0 46.5 18t23.5 44l9 66q13 5 24.5 12t22.5 15l62-26q25-11 50-2t39 32l47 82q14 23 8 49t-27 43l-53 40q1 7 1 13.5v27q0 6.5-2 13.5l53 40q21 17 27 43t-8 49l-48 82q-14 23-39 32t-50-2l-60-26q-11 8-23 15t-24 12l-9 66q-4 26-23.5 44T527-80h-94Zm7-80h79l14-106q31-8 57.5-23.5T639-327l99 41 39-68-86-65q5-14 7-29.5t2-31.5q0-16-2-31.5t-7-29.5l86-65-39-68-99 42q-22-23-48.5-38.5T533-694l-13-106h-79l-14 106q-31 8-57.5 23.5T321-633l-99-41-39 68 86 64q-5 15-7 30t-2 32q0 16 2 31t7 30l-86 65 39 68 99-42q22 23 48.5 38.5T427-266l13 106Zm42-180q58 0 99-41t41-99q0-58-41-99t-99-41q-59 0-99.5 41T342-480q0 58 40.5 99t99.5 41Zm-2-140Z' fill='currentColor'/><circle cx='12' cy='12' r='2.5' fill='none' stroke='currentColor' stroke-width='1.5'/><circle cx='12' cy='12' r='2.5' fill='none' stroke='currentColor' stroke-width='1.5'/></svg>\";b.setAttribute('aria-label','Settings');const i=b.querySelector('svg');i.style.width='28px';i.style.height='28px';i.style.display='block'}})()", null);
                view.evaluateJavascript("(()=>{const s=document.createElement('style');s.textContent='.root-done{display:none;border-radius:14px;padding:17px;margin-bottom:14px;font-size:16px;font-weight:800}.root-done.show{display:block}.root-done.ok{border:1px solid #269c73;background:#103a2d;color:#53e0a9}.root-done.bad{border:1px solid #a33a52;background:#3a1723;color:#ff7890}';document.head.appendChild(s);const r=document.getElementById('root');if(r&&!document.getElementById('rootDone')){const b=document.createElement('div');b.id='rootDone';b.className='root-done';r.insertBefore(b,r.firstElementChild)}const old=window.render;window.render=function(id,v){old(id,v);if(id==='rootOut'){try{const x=JSON.parse(v),b=document.getElementById('rootDone');if(b){b.className='root-done show '+(x.ok?'ok':'bad');b.textContent=x.ok?'✓ Root available':'✕ Root unavailable'}}catch(e){}}}})()", null);
                view.evaluateJavascript("(()=>{const card=document.querySelector('#install .card'),apply=document.querySelector('#install button.primary');if(!card||!apply||document.getElementById('checkRequirements'))return;const check=document.createElement('button');check.id='checkRequirements';check.textContent='Check requirements';apply.disabled=true;apply.style.opacity='.45';const out=document.createElement('div');out.id='installReady';out.className='result';out.textContent='Check requirements before applying authorization.';card.insertBefore(check,apply);card.insertBefore(out,apply);const code=document.getElementById('unlockCode');function gate(){apply.disabled=true;apply.style.opacity='.45';out.className='result';out.textContent='Checking device, root access, authorization and unlock code…';const validCode=/^[0-9a-fA-F]{632}$/.test((code.value||'').replace(/\\s+/g,''));const auth=DeepTest.hasAuth();const cb='installRoot'+Date.now();window[cb]=v=>{try{const x=JSON.parse(v),root=!!x.ok,ready=validCode&&auth&&root;out.className='result '+(ready?'ok':'bad');out.textContent=ready?'✓ Everything is ready. Apply authorization is enabled.':('Not ready — '+(!auth?'auth.json is missing. ': '')+(!validCode?'unlock code must be 632 hexadecimal characters. ':'')+(!root?'temporary root is unavailable.':''));apply.disabled=!ready;apply.style.opacity=ready?'1':'.45'}catch(e){out.className='result bad';out.textContent='Could not verify requirements.'}delete window[cb]};DeepTest.rootCheck(cb)}check.onclick=gate;code.addEventListener('input',()=>{apply.disabled=true;apply.style.opacity='.45'})})()", null);
                view.evaluateJavascript("(()=>{const c=document.querySelector('#install .card'),check=document.getElementById('checkRequirements'),apply=document.querySelector('#install button.primary'),out=document.getElementById('installReady');if(!c||!check||!apply||!out||document.getElementById('installActions'))return;const row=document.createElement('div');row.id='installActions';row.style.cssText='display:flex;align-items:center;gap:8px;flex-wrap:wrap';c.insertBefore(row,check);row.append(check,apply)})()", null);
                view.evaluateJavascript("(()=>{const o=document.getElementById('installReady');if(!o)return;const ready='✓ Root available\\n✓ Unlock code ready\\n✓ Authorization ready — Apply authorization is enabled.';new MutationObserver(()=>{if(o.classList.contains('ok')&&o.textContent!==ready)o.textContent=ready}).observe(o,{attributes:true,childList:true,subtree:true})})()", null);
                view.evaluateJavascript("(()=>{const s=document.createElement('style');s.textContent='.dt-spinner{display:block;flex:0 0 24px;width:24px;height:24px;aspect-ratio:1;border:3px solid currentColor;border-right-color:transparent;border-radius:50%;animation:dtspin .7s linear infinite}.dt-loading{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9999;display:flex;align-items:center;gap:12px;padding:14px 20px;border:1px solid #5140a5;border-radius:14px;background:#17152b;color:#fff;font-weight:800;box-shadow:0 10px 35px #0008}button{transition:filter .12s ease,background-color .12s ease!important}button:active{filter:brightness(1.16)!important}.nav button:active{filter:none!important}.dt-busy{filter:brightness(1.16)!important;cursor:wait!important}@keyframes dtspin{to{transform:rotate(360deg)}}';document.head.appendChild(s);const oldApi=window.api,oldRender=window.render;let active=null;let lastButton=null;document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('#request button'))lastButton=e.target.closest('#request button')},true);window.api=function(action,data,out){if(out==='requestOut'&&lastButton){active=lastButton;active.disabled=true;active.classList.add('dt-busy');if(!document.getElementById('dtLoading')){const l=document.createElement('div');l.id='dtLoading';l.className='dt-loading';l.innerHTML='<span class=dt-spinner></span><span>Working…</span>';document.body.appendChild(l)}}return oldApi(action,data,out)};window.render=function(id,v){oldRender(id,v);if(id==='requestOut'&&active){active.disabled=false;active.classList.remove('dt-busy');const l=document.getElementById('dtLoading');if(l)l.remove();active=null}}})()", null);
            }
        });
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.setBackgroundColor(Color.rgb(8, 11, 18));
        web.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(
                    insets.getSystemWindowInsetLeft(),
                    insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(),
                    insets.getSystemWindowInsetBottom()
            );
            return insets.consumeSystemWindowInsets();
        });
        web.addJavascriptInterface(new Bridge(), "DeepTest");
        web.loadUrl("file:///android_asset/index.html");
        setContentView(web);
    }

    private void deliver(String callback, String result) {
        runOnUiThread(() -> web.evaluateJavascript(callback + "(" + JSONObject.quote(result) + ")", null));
    }

    private JSONObject readObject(File file) {
        if (!file.isFile()) return null;
        try {
            return new JSONObject(new String(java.nio.file.Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8));
        } catch (Exception ignored) {
            return null;
        }
    }

    private String firstValue(JSONObject object, String... keys) {
        if (object == null) return "";
        for (String key : keys) {
            String value = object.optString(key, "").trim();
            if (!value.isEmpty()) return value;
        }
        return "";
    }

    private void writePrivateObject(File target, JSONObject value) throws Exception {
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs())
            throw new IOException("Could not create private token storage.");
        File temporary = new File(parent, "." + target.getName() + ".import");
        try (FileOutputStream output = new FileOutputStream(temporary)) {
            output.write((value.toString(2) + "\n").getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
        if (!temporary.renameTo(target)) {
            temporary.delete();
            throw new IOException("Could not restore " + target.getName() + ".");
        }
        target.setReadable(false, false);
        target.setWritable(false, false);
        target.setReadable(true, true);
        target.setWritable(true, true);
    }

    private JSONObject backupObject(JSONObject container, String key) {
        Object value = container.opt(key);
        if (value instanceof JSONObject) return (JSONObject) value;
        if (value instanceof String) {
            try { return new JSONObject((String) value); }
            catch (Exception ignored) {}
        }
        return null;
    }

    private String accountIdentity() {
        File root = new File(getFilesDir(), "auth");
        JSONObject primary = readObject(new File(root, "primary-auth.json"));
        String value = firstValue(primary, "account_name", "accountName", "user_name", "userName");
        if (!value.isEmpty()) return value;

        JSONObject session = readObject(new File(root, "login-session.json"));
        value = firstValue(session, "account_id", "accountId");
        if (!value.isEmpty()) return value;

        JSONObject business = readObject(new File(root, "auth.json"));
        value = firstValue(business, "account_name", "accountName", "email", "phone_number");
        if (!value.isEmpty()) return value;
        String idToken = firstValue(business, "id_token", "idToken");
        try {
            String[] pieces = idToken.split("\\.");
            if (pieces.length > 1) {
                byte[] decoded = android.util.Base64.decode(pieces[1], android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
                JSONObject claims = new JSONObject(new String(decoded, StandardCharsets.UTF_8));
                value = firstValue(claims, "email", "phone_number", "preferred_username", "accountName", "user_name", "name");
                if (!value.isEmpty()) return value;
            }
        } catch (Exception ignored) {}
        return "Imported HeyTap account";
    }

    private String readTextAsset(String name) throws IOException {
        try (InputStream input = getAssets().open(name);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == EXPORT_JSON) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && exportPayload != null) {
                try (OutputStream out = getContentResolver().openOutputStream(data.getData())) {
                    if (out != null) out.write(exportPayload.getBytes(StandardCharsets.UTF_8));
                    deliver("window.onSettingsExport", "{\"ok\":true,\"message\":\"Settings exported successfully.\"}");
                } catch (Exception e) { deliver("window.onSettingsExport", "{\"ok\":false,\"error\":" + JSONObject.quote(e.getMessage()) + "}"); }
            }
            return;
        }
        if (requestCode != PICK_AUTH && requestCode != PICK_PROFILE) return;
        String result;
        try {
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                result = "{\"ok\":false,\"error\":\"Import cancelled.\"}";
            } else {
                File targetDir = new File(getFilesDir(), "auth");
                if (!targetDir.exists() && !targetDir.mkdirs()) throw new IOException("Could not create private token storage.");
                String displayName = "";
                try (android.database.Cursor cursor = getContentResolver().query(data.getData(), new String[]{"_display_name"}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) displayName = cursor.getString(0);
                }
                byte[] payload;
                try (InputStream input = getContentResolver().openInputStream(data.getData())) {
                    if (input == null) throw new IOException("Could not open selected file.");
                    payload = input.readAllBytes();
                }
                JSONObject selected = new JSONObject(new String(payload, StandardCharsets.UTF_8));
                boolean backup = "deeptest2-backup".equals(selected.optString("format")) ||
                        (selected.has("auth") && selected.has("settings"));
                if (backup) {
                    JSONObject auth = backupObject(selected, "auth");
                    if (auth == null) throw new IOException("Backup does not contain a valid auth.json object.");
                    writePrivateObject(new File(targetDir, "auth.json"), auth);
                    JSONObject settings = backupObject(selected, "settings");
                    if (settings != null) writePrivateObject(new File(targetDir, "gui-settings.json"), settings);
                    JSONObject primary = backupObject(selected, "primaryAuth");
                    if (primary != null) writePrivateObject(new File(targetDir, "primary-auth.json"), primary);
                    JSONObject session = backupObject(selected, "loginSession");
                    if (session != null) writePrivateObject(new File(targetDir, "login-session.json"), session);
                    result = "{\"ok\":true,\"message\":\"DeepTest account and settings backup restored.\"}";
                } else {
                    File target = new File(targetDir, displayName.toLowerCase().contains("gui-settings") ? "gui-settings.json" : (requestCode == PICK_AUTH ? "auth.json" : "gui-settings.json"));
                    writePrivateObject(target, selected);
                    result = "{\"ok\":true,\"message\":\"JSON profile imported into private app storage.\"}";
                }
            }
        } catch (Exception error) {
            result = "{\"ok\":false,\"error\":" + JSONObject.quote(error.getMessage()) + "}";
        }
        deliver("window.onAuthImported", result);
    }

    public class Bridge {
        @JavascriptInterface public String deviceInfo() {
            return RootOps.deviceInfo(MainActivity.this);
        }
        @JavascriptInterface public String requestProfile() {
            JSONObject profile = readObject(new File(getFilesDir(), "auth/gui-settings.json"));
            return profile == null ? "{}" : profile.toString();
        }
        @JavascriptInterface public boolean hasAuth() {
            return new File(getFilesDir(), "auth/auth.json").isFile();
        }
        @JavascriptInterface public String accountInfo() {
            try {
                boolean authorized = new File(getFilesDir(), "auth/auth.json").isFile();
                JSONObject result = new JSONObject().put("authorized", authorized);
                if (authorized) result.put("account", accountIdentity());
                else result.put("message", "Not signed in.");
                return result.toString();
            } catch (Exception ignored) {
                return "{\"authorized\":false,\"message\":\"Could not read account status.\"}";
            }
        }
        @JavascriptInterface public String logoutAccount() {
            try {
                File root = new File(getFilesDir(), "auth");
                String[] names = {"auth.json", "primary-auth.json", "login-session.json"};
                for (String name : names) {
                    File target = new File(root, name);
                    if (target.exists() && !target.delete()) throw new IOException("Could not remove " + name + ".");
                }
                File[] leftovers = root.listFiles((dir, name) ->
                        name.startsWith(".auth-") || name.startsWith(".primary-auth.json-") || name.startsWith(".login-session.json-"));
                if (leftovers != null) for (File file : leftovers) file.delete();
                return "{\"ok\":true,\"message\":\"Logged out. Local HeyTap authorization was removed.\"}";
            } catch (Exception error) {
                try { return new JSONObject().put("ok", false).put("error", error.getMessage()).toString(); }
                catch (Exception ignored) { return "{\"ok\":false}"; }
            }
        }
        @JavascriptInterface public String openSourceLicenses() {
            try {
                return readTextAsset("licenses/third-party-notices.txt") +
                        "\n\n============================================================\n\n" +
                        readTextAsset("licenses/ghostlock-LICENSE.txt");
            } catch (Exception error) {
                return "Could not load the bundled open-source license.\n\n" + error.getMessage();
            }
        }
        @JavascriptInterface public void openExternalUrl(String value) {
            try {
                Uri uri = Uri.parse(value == null ? "" : value);
                String scheme = uri.getScheme();
                if (!"https".equalsIgnoreCase(scheme) && !"http".equalsIgnoreCase(scheme)) return;
                runOnUiThread(() -> startActivity(new Intent(Intent.ACTION_VIEW, uri)));
            } catch (Exception ignored) {}
        }
        @JavascriptInterface public void setBrightMode(boolean bright) {
            runOnUiThread(() -> {
                getWindow().setStatusBarColor(Color.parseColor(bright ? "#f4f6fb" : "#080b12"));
                getWindow().setNavigationBarColor(Color.parseColor(bright ? "#f4f6fb" : "#080b12"));
                int flags = bright ? android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR : 0;
                getWindow().getDecorView().setSystemUiVisibility(flags);
            });
        }
        @JavascriptInterface public void exportSettings(String currentProfile) {
            try {
                File auth = new File(getFilesDir(), "auth/auth.json");
                File profile = new File(getFilesDir(), "auth/gui-settings.json");
                File primary = new File(getFilesDir(), "auth/primary-auth.json");
                File session = new File(getFilesDir(), "auth/login-session.json");
                JSONObject authObject = readObject(auth);
                if (authObject == null) throw new IOException("Sign in or import auth.json before exporting a backup.");
                JSONObject profileObject = readObject(profile);
                if (profileObject == null) profileObject = new JSONObject();
                JSONObject liveProfile = new JSONObject(currentProfile == null ? "{}" : currentProfile);
                java.util.Iterator<String> keys = liveProfile.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    String value = liveProfile.optString(key, "").trim();
                    if (!value.isEmpty() && profileObject.optString(key, "").trim().isEmpty())
                        profileObject.put(key, value);
                }
                JSONObject bundle = new JSONObject()
                        .put("format", "deeptest2-backup")
                        .put("version", 1)
                        .put("auth", authObject)
                        .put("settings", profileObject);
                JSONObject primaryObject = readObject(primary);
                if (primaryObject != null) bundle.put("primaryAuth", primaryObject);
                JSONObject sessionObject = readObject(session);
                if (sessionObject != null) bundle.put("loginSession", sessionObject);
                exportPayload = bundle.toString(2);
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.setType("application/json"); intent.putExtra(Intent.EXTRA_TITLE, "deeptest2-backup.json");
                startActivityForResult(intent, EXPORT_JSON);
            } catch (Exception e) { deliver("window.onSettingsExport", "{\"ok\":false,\"error\":" + JSONObject.quote(e.getMessage()) + "}"); }
        }
        @JavascriptInterface public void api(String action, String json, String callback) {
            worker.execute(() -> {
                try {
                    PyObject module = Python.getInstance().getModule("android_bridge");
                    String out = module.callAttr("dispatch", action, json, getFilesDir().getAbsolutePath()).toString();
                    deliver(callback, out);
                } catch (Throwable error) {
                    deliver(callback, "{\"ok\":false,\"error\":" + JSONObject.quote(error.toString()) + "}");
                }
            });
        }
        @JavascriptInterface public void pickAuth() {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/json");
            startActivityForResult(intent, PICK_AUTH);
        }
        @JavascriptInterface public void pickProfile() {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/json");
            startActivityForResult(intent, PICK_PROFILE);
        }
        @JavascriptInterface public void rootCheck(String callback) {
            worker.execute(() -> deliver(callback, RootOps.rootCheck(MainActivity.this)));
        }
        @JavascriptInterface public void gainTempRoot(String callback) {
            worker.execute(() -> deliver(callback, RootOps.gainTempRoot(MainActivity.this)));
        }
        @JavascriptInterface public void installAuthorization(String code, String callback) {
            worker.execute(() -> deliver(callback, RootOps.install(MainActivity.this, code)));
        }
        @JavascriptInterface public void rebootBootloader(String callback) {
            worker.execute(() -> deliver(callback, RootOps.rebootBootloader(MainActivity.this)));
        }
    }
}
