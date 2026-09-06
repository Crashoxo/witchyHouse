using UnityEditor;
using UnityEngine;

/// <summary>
/// 把專案切成 2D 模式。
///
/// 這個專案是用手刻的骨架建的（不是從 Unity 的 2D 範本開的），所以 ProjectSettings 裡
/// m_DefaultBehaviorMode 還是 0 ＝ 3D。場景本身是對的（正交攝影機、純色背景），
/// 但專案層級是 3D 會有三個實際影響：
///
///   1. 新建場景會自動附天空盒 + 平行光
///   2. **Resources 以外**的圖匯入時會被當成 3D 貼圖，不是 Sprite
///      （Resources 底下的有 PixelArtImporter 擋著，不受影響）
///   3. Scene 視窗預設是 3D 透視，不是平面
///
/// ⚠️ 為什麼用選單指令而不是直接改 ProjectSettings/EditorSettings.asset：
///    Unity 執行中會把 ProjectSettings 快取在記憶體，退出時整包寫回硬碟 ——
///    在它開著的時候手改檔案，改動會被覆蓋掉。走 API 才會即時生效並正確存檔。
///
/// 用法：選單 Witch Shop → 設定成 2D 專案
/// </summary>
public static class Setup2DProject
{
    [MenuItem("Witch Shop/設定成 2D 專案")]
    public static void Apply()
    {
        EditorSettings.defaultBehaviorMode = EditorBehaviorMode.Mode2D;

        // Scene 視窗切成平面檢視（這是「每個視窗」的設定，不是專案設定）
        if (SceneView.lastActiveSceneView != null)
        {
            SceneView.lastActiveSceneView.in2DMode = true;
            SceneView.lastActiveSceneView.Repaint();
        }

        AssetDatabase.SaveAssets();

        Debug.Log("[Setup2DProject] 已切成 2D 模式。\n" +
                  "・新場景不會再附天空盒與平行光\n" +
                  "・之後匯入的圖預設是 Sprite\n" +
                  "・Scene 視窗已切成平面檢視");
    }

    /// <summary>目前是不是 2D 模式（選單上會打勾）。</summary>
    [MenuItem("Witch Shop/設定成 2D 專案", true)]
    static bool Validate()
    {
        Menu.SetChecked("Witch Shop/設定成 2D 專案",
                        EditorSettings.defaultBehaviorMode == EditorBehaviorMode.Mode2D);
        return true;
    }
}
