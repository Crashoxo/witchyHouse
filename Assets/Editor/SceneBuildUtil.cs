using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>
/// 場景建構的共用工具。
///
/// ⚠️ **Unity 跟 Cocos 很不一樣的一點**：Cocos 的 `director.loadScene('town')` 只要
///    場景檔存在就能切；Unity 的 `SceneManager.LoadScene("town")` 要求那個場景
///    **有登記在 Build Settings 裡**，沒登記的話執行期會直接丟錯。
///    所以每個 SceneBuilder 建完場景都要呼叫 Register()。
/// </summary>
public static class SceneBuildUtil
{
    /// <summary>
    /// 把場景加進 Build Settings（已經在裡面就跳過）。
    ///
    /// ⚠️ 一定要先 AssetDatabase.Refresh()：剛 SaveScene 出來的場景還沒進 AssetDatabase，
    ///    這時建立的 EditorBuildSettingsScene 拿不到 GUID，序列化時會被**靜默丟掉** ——
    ///    看起來登記成功了，重開卻不見，然後執行期 LoadScene 直接失敗。踩過一次。
    /// </summary>
    public static void Register(string path)
    {
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        var guid = AssetDatabase.AssetPathToGUID(path);
        if (string.IsNullOrEmpty(guid))
        {
            Debug.LogError($"[SceneBuildUtil] {path} 還沒進 AssetDatabase，登記失敗。" +
                           "跑一次選單 Witch Shop → 重新登記所有場景。");
            return;
        }

        var list = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
        foreach (var s in list)
            if (s.path == path) { s.enabled = true; EditorBuildSettings.scenes = list.ToArray(); return; }

        list.Add(new EditorBuildSettingsScene(path, true));
        EditorBuildSettings.scenes = list.ToArray();
        Debug.Log($"[SceneBuildUtil] 已把 {path} 加進 Build Settings");
    }

    /// <summary>
    /// 掃描 Assets/Scenes 底下所有場景，全部登記進 Build Settings。
    /// 上面那個 GUID 時序問題的保險絲 —— 覺得換場怪怪的就跑這個。
    /// </summary>
    [MenuItem("Witch Shop/重新登記所有場景")]
    public static void RegisterAll()
    {
        AssetDatabase.Refresh();
        var list = new List<EditorBuildSettingsScene>();
        foreach (var g in AssetDatabase.FindAssets("t:Scene", new[] { "Assets/Scenes" }))
        {
            var path = AssetDatabase.GUIDToAssetPath(g);
            list.Add(new EditorBuildSettingsScene(path, true));
        }
        EditorBuildSettings.scenes = list.ToArray();

        var names = new List<string>();
        foreach (var s in list) names.Add(System.IO.Path.GetFileNameWithoutExtension(s.path));
        Debug.Log($"[SceneBuildUtil] Build Settings 現在有 {list.Count} 個場景：{string.Join(", ", names)}");
    }

    /// <summary>
    /// 擺一張圖。
    ///
    /// ⚠️ sortingOrder 用 -y 算（YSort）：站得低的畫在前面，
    ///    女巫走到樹/房子後面時才會被擋住。
    /// </summary>
    public static GameObject MakeSprite(string art, float x, float y, float scale, Transform parent)
    {
        var sp = LoadSprite(art);
        if (sp == null) return null;
        var go = new GameObject(System.IO.Path.GetFileName(art));
        go.transform.SetParent(parent);
        go.transform.position = new Vector3(x, y, 0f);
        go.transform.localScale = new Vector3(scale, scale, 1f);
        var sr = go.AddComponent<SpriteRenderer>();
        sr.sprite = sp;
        sr.sortingOrder = Mathf.RoundToInt(-y);
        return go;
    }

    /// <summary>
    /// ⚠️ 一定要 Resources.Load&lt;Sprite&gt;，不能用 Sprite.Create ——
    ///    後者生的不是資產，存進場景後重開會變 null。
    /// </summary>
    public static Sprite LoadSprite(string resourcePath)
    {
        var sp = Resources.Load<Sprite>(resourcePath);
        if (sp == null) Debug.LogWarning($"[SceneBuildUtil] 找不到 {resourcePath}");
        return sp;
    }
}
