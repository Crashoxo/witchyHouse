using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// 一鍵建網頁版（WebGL）。
///
/// 用法：選單 Witch Shop → 建置 → 網頁版（WebGL）
///
/// ⚠️ **第一次建會很久**（15～40 分鐘）：WebGL 要把整個 C# 專案透過 IL2CPP
///    翻成 C++ 再編成 WebAssembly。之後的增量建置會快很多。
///
/// ⚠️ 建好之後**不能直接用檔案總管點開 index.html** —— 瀏覽器的 file:// 協定
///    擋掉 WebAssembly 需要的載入方式。要用「建置並執行」（Unity 會自己開一個
///    本機伺服器），或自己起一個靜態伺服器。見選單裡的「網頁版（建好直接開瀏覽器）」。
/// </summary>
public static class WebBuilder
{
    const string OutDir = "Build/Web";

    [MenuItem("Witch Shop/建置/網頁版（WebGL）")]
    public static void BuildWeb() => Run(false);

    [MenuItem("Witch Shop/建置/網頁版（建好直接開瀏覽器）")]
    public static void BuildAndRunWeb() => Run(true);

    static void Run(bool autoRun)
    {
        SceneBuildUtil.RegisterAll();          // 確保五張地圖都在 Build Settings 裡

        var scenes = EditorBuildSettings.scenes;
        if (scenes.Length == 0)
        {
            Debug.LogError("[WebBuilder] Build Settings 裡沒有場景，先跑 Witch Shop → 重新登記所有場景");
            return;
        }

        // ── 網頁版設定 ─────────────────────────────────────────
        PlayerSettings.companyName = "Crash";
        PlayerSettings.productName = "魔女商店";

        // 設計解析度 960×640（同遊戲內的 PanelSettings）
        PlayerSettings.defaultWebScreenWidth = 960;
        PlayerSettings.defaultWebScreenHeight = 640;
        PlayerSettings.runInBackground = true;

        // ⚠️ 壓縮先關掉：Brotli/Gzip 需要伺服器送對 Content-Encoding 標頭，
        //    本機測試最容易卡在這裡（畫面一片黑、Console 說載入失敗）。
        //    真的要放上網站再開，並照 Unity 文件設好伺服器。
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.dataCaching = true;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.ExplicitlyThrownExceptionsOnly;

        var paths = new string[scenes.Length];
        for (int i = 0; i < scenes.Length; i++) paths[i] = scenes[i].path;

        Directory.CreateDirectory(OutDir);

        var opts = new BuildPlayerOptions
        {
            scenes = paths,
            locationPathName = OutDir,
            target = BuildTarget.WebGL,
            options = autoRun ? BuildOptions.AutoRunPlayer : BuildOptions.None,
        };

        Debug.Log($"[WebBuilder] 開始建置網頁版 → {Path.GetFullPath(OutDir)}\n" +
                  $"場景 {paths.Length} 個。⚠️ 第一次會跑很久（15~40 分鐘），Unity 會像當掉一樣，別關它。");

        var report = BuildPipeline.BuildPlayer(opts);
        var s = report.summary;

        if (s.result == BuildResult.Succeeded)
        {
            Debug.Log($"[WebBuilder] 建置成功！\n" +
                      $"輸出：{Path.GetFullPath(OutDir)}\n" +
                      $"大小：{s.totalSize / 1048576} MB　耗時：{s.totalTime:hh\\:mm\\:ss}\n" +
                      (autoRun ? "瀏覽器應該自己開了。" :
                       "⚠️ 不要直接點 index.html —— 要用「建好直接開瀏覽器」那個選單，" +
                       "或自己起一個本機伺服器（見 Witch Shop → 建置 → 怎麼開網頁版）。"));
            EditorUtility.RevealInFinder(Path.GetFullPath(OutDir));
        }
        else
        {
            Debug.LogError($"[WebBuilder] 建置失敗：{s.result}，錯誤 {s.totalErrors} 個。看上面的 Console。");
        }
    }

    [MenuItem("Witch Shop/建置/怎麼開網頁版")]
    public static void HowTo()
    {
        Debug.Log(
            "網頁版建好之後怎麼玩：\n\n" +
            "① 最簡單：選單 Witch Shop → 建置 → 網頁版（建好直接開瀏覽器）\n" +
            "   Unity 會自己起一個本機伺服器並開瀏覽器。\n\n" +
            "② 已經建好了想再開一次：在 " + Path.GetFullPath(OutDir) + " 這個資料夾裡\n" +
            "   開命令列跑（擇一）：\n" +
            "     python -m http.server 8080\n" +
            "     npx serve -l 8080\n" +
            "   然後瀏覽器開 http://localhost:8080\n\n" +
            "⚠️ 直接點兩下 index.html 是**不會動的** —— 瀏覽器的 file:// 協定\n" +
            "   擋掉 WebAssembly 需要的載入方式，畫面會一片黑。\n\n" +
            "③ 要放到網路上：把整個 Build/Web 資料夾丟上任何靜態空間\n" +
            "   （GitHub Pages / itch.io / Netlify 都可以）。itch.io 對 Unity WebGL\n" +
            "   支援最好，上傳 zip 就能玩。");
    }
}
