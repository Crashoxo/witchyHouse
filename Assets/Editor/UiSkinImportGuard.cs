using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>
/// 修 UI 外觀圖（Resources/ui/skin8/）的匯入競態：PPU 要 100、網格要 FullRect，
/// 值本身由 PixelArtImporter 的例外負責設，這支只負責「發現不對就叫它重匯入一次」。
///
/// 為什麼需要：tools/gen_ui_skin.py 產生的新圖跟改過的 PixelArtImporter.cs 常常同時進專案，
/// Unity 會**先用舊的已編譯 importer** 把圖匯入（PPU 1，還把 .meta 寫成 1），
/// 等 importer 重新編譯好之後也不會自動重匯入 —— 畫面就一直是 UI Toolkit 九宮格 ×100 的大色塊（實機踩過）。
/// domain reload 之後 importer 一定是最新編譯版，這時重匯入就會走到正確的例外。
///
/// ⚠️ 這裡刻意不自己寫入 PPU／meshType：設定只有 PixelArtImporter 一份，免得兩邊不同步。
/// ⚠️ 每張圖每次 domain reload 最多重匯入一次：要是 importer 的例外被刪掉，重匯入永遠修不好，
///    沒有這道防護就會無限重匯入。第二次還是不對就只警告一次，然後不再碰它。
/// </summary>
[InitializeOnLoad]
public static class UiSkinImportGuard
{
    const string Folder = "Assets/Resources/ui/skin8";
    const float WantPpu = 100f;

    // static 欄位每次 domain reload 都會清空 —— 剛好就是「每次 reload 最多一次」的範圍
    static readonly HashSet<string> s_reimported = new HashSet<string>();
    static readonly HashSet<string> s_warned = new HashSet<string>();
    static bool s_waitingForEditMode;

    static UiSkinImportGuard()
    {
        // 建構子跑的時候 AssetDatabase 可能還在忙，延到下一個編輯器更新再看
        EditorApplication.delayCall += CheckAll;
    }

    [MenuItem("Witch Shop/工具/重匯入 UI 外觀圖")]
    public static void ForceReimportAll()
    {
        if (!AssetDatabase.IsValidFolder(Folder))
        {
            Debug.LogWarning($"[UiSkinImportGuard] 找不到 {Folder}，沒有東西可以重匯入");
            return;
        }
        var paths = FindSkinTextures();
        // 手動按的就是想重來：清掉警告紀錄，重匯入後若仍不對會再警告一次
        s_warned.Clear();
        foreach (var p in paths) s_reimported.Add(p);
        Reimport(paths);
        Debug.Log($"[UiSkinImportGuard] 已強制重匯入 {paths.Count} 張 UI 外觀圖");
    }

    /// <summary>掃整個 skin8 資料夾（domain reload 後、離開 Play 模式後）。</summary>
    static void CheckAll()
    {
        if (!ReadyOrDefer(CheckAll)) return;
        if (!AssetDatabase.IsValidFolder(Folder)) return;   // 還沒產生過外觀圖：安靜返回
        Check(FindSkinTextures());
    }

    /// <summary>
    /// 檢查一批路徑，不對的重匯入（每張每次 reload 最多一次），第二次還不對就警告。
    /// </summary>
    static void Check(IEnumerable<string> paths)
    {
        var todo = new List<string>();
        foreach (var path in paths)
        {
            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti == null || IsCorrect(ti)) continue;

            if (s_reimported.Contains(path))
            {
                // 已經重匯入過還是不對 → 多半是 PixelArtImporter 的 skin8 例外不見了，再匯入也沒用
                if (s_warned.Add(path))
                    Debug.LogWarning($"[UiSkinImportGuard] {path} 重匯入後 PPU 仍是 {ti.spritePixelsPerUnit}" +
                                     $"（要 {WantPpu}、FullRect）。請確認 PixelArtImporter.cs 的 /Resources/ui/skin8/ 例外還在；" +
                                     "這次 domain reload 內不再自動重匯入它。");
                continue;
            }
            s_reimported.Add(path);
            todo.Add(path);
        }
        if (todo.Count == 0) return;   // 沒事就不印

        Reimport(todo);
        Debug.Log($"[UiSkinImportGuard] 重匯入 {todo.Count} 張 UI 外觀圖（PPU 要 {WantPpu}）");
    }

    static bool IsCorrect(TextureImporter ti)
    {
        if (!Mathf.Approximately(ti.spritePixelsPerUnit, WantPpu)) return false;
        // spriteMeshType 沒有直接的屬性，要走 TextureImporterSettings（跟 PixelArtImporter 同一條路）
        var st = new TextureImporterSettings();
        ti.ReadTextureSettings(st);
        return st.spriteMeshType == SpriteMeshType.FullRect;
    }

    static void Reimport(List<string> paths)
    {
        if (paths.Count == 0) return;
        AssetDatabase.StartAssetEditing();
        try
        {
            foreach (var p in paths)
                AssetDatabase.ImportAsset(p, ImportAssetOptions.ForceUpdate);
        }
        finally
        {
            // ⚠️ 一定要成對：漏掉 StopAssetEditing 的話 AssetDatabase 會一直卡在暫停匯入的狀態
            AssetDatabase.StopAssetEditing();
        }
    }

    static List<string> FindSkinTextures()
    {
        var list = new List<string>();
        foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { Folder }))
            list.Add(AssetDatabase.GUIDToAssetPath(guid));
        return list;
    }

    /// <summary>
    /// 能動手就回 true；Play 模式中改掛到回編輯模式後，編譯／匯入中則下一幀再試。
    /// </summary>
    static bool ReadyOrDefer(EditorApplication.CallbackFunction retry)
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            // Play 中重匯入 Resources 的圖會打斷遊戲裡正在用的 Sprite，等離開 Play 再整批檢查
            if (!s_waitingForEditMode)
            {
                s_waitingForEditMode = true;
                EditorApplication.playModeStateChanged += OnPlayModeChanged;
            }
            return false;
        }
        if (EditorApplication.isCompiling || EditorApplication.isUpdating)
        {
            EditorApplication.delayCall += retry;
            return false;
        }
        return true;
    }

    static void OnPlayModeChanged(PlayModeStateChange change)
    {
        if (change != PlayModeStateChange.EnteredEditMode) return;
        EditorApplication.playModeStateChanged -= OnPlayModeChanged;
        s_waitingForEditMode = false;
        // 離開 Play 期間可能進來的新圖也一起掃
        EditorApplication.delayCall += CheckAll;
    }

    /// <summary>
    /// 產生器新增／改動 skin8 圖時，匯入完就檢查，不用等下一次 domain reload。
    /// 重匯入觸發的那一輪也會回到這裡 —— 正好用來驗「重匯入後仍不對 → 警告」。
    /// </summary>
    class Postprocessor : AssetPostprocessor
    {
        static void OnPostprocessAllAssets(string[] imported, string[] deleted, string[] moved, string[] movedFrom)
        {
            List<string> hits = null;
            Collect(imported, ref hits);
            Collect(moved, ref hits);
            if (hits == null) return;

            // ⚠️ 不在 OnPostprocessAllAssets 裡直接 ImportAsset（還在匯入流程中，巢狀匯入容易出事），延到下一幀
            EditorApplication.delayCall += () =>
            {
                if (!ReadyOrDefer(CheckAll)) return;   // Play 中／忙碌時退回整批掃描
                Check(hits);
            };
        }

        static void Collect(string[] paths, ref List<string> hits)
        {
            foreach (var p in paths)
            {
                if (!p.StartsWith(Folder + "/", System.StringComparison.Ordinal)) continue;
                (hits ??= new List<string>()).Add(p);
            }
        }
    }
}
