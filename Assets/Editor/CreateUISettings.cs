using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.UIElements;

/// <summary>
/// 建立 UI Toolkit 要用的 PanelSettings 資產。
///
/// UIDocument 一定要掛一個 PanelSettings 才畫得出東西（它決定解析度對應、縮放模式、
/// 排序等等）。這個東西只能是「專案裡的資產」，不能在執行期 new 出來就用，
/// 所以做成選單指令生一次，之後 BagPanel 用 Resources.Load 拿。
///
/// 用法：選單 Witch Shop → 建立 UI 設定檔
/// </summary>
public static class CreateUISettings
{
    const string Dir = "Assets/Resources/ui";
    const string Path_ = Dir + "/UIPanelSettings.asset";

    [MenuItem("Witch Shop/建立 UI 設定檔")]
    public static void Create()
    {
        Directory.CreateDirectory(Dir);

        var ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(Path_);
        bool isNew = ps == null;
        if (isNew) ps = ScriptableObject.CreateInstance<PanelSettings>();

        // 跟遊戲同一套設計解析度（Cocos 版是 960×640 fitHeight）。
        // ScaleWithScreenSize + matchHeight=1 ＝ 以高度為準等比縮放，跟 fitHeight 對應。
        ps.scaleMode = PanelScaleMode.ScaleWithScreenSize;
        ps.referenceResolution = new Vector2Int(960, 640);
        ps.screenMatchMode = PanelScreenMatchMode.MatchWidthOrHeight;
        ps.match = 1f;                 // 1 = 完全以高度為準
        ps.sortingOrder = 100;         // UI 疊在遊戲畫面之上

        // 預設主題（沒有它按鈕會沒有外觀基底）
        var theme = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(
            "Packages/com.unity.ui/PackageResources/StyleSheets/Generated/DefaultRuntimeTheme.tss");
        if (theme == null)
            theme = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>("Assets/UI Toolkit/UnityThemes/UnityDefaultRuntimeTheme.tss");
        if (theme != null) ps.themeStyleSheet = theme;
        else Debug.LogWarning("[CreateUISettings] 找不到預設 RuntimeTheme —— " +
                              "若 UI 看起來沒有樣式，去 Assets → Create → UI Toolkit → TSS 建一個再指過來。");

        if (isNew) AssetDatabase.CreateAsset(ps, Path_);
        else EditorUtility.SetDirty(ps);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log($"[CreateUISettings] {(isNew ? "已建立" : "已更新")} {Path_}");
    }
}
