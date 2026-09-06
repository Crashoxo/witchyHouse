using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;

/// <summary>
/// 一鍵建出「切片」測試場景：地面 + 女巫 + 攝影機。
///
/// Cocos 版的六個場景檔內容幾乎都是空的（東西全由程式碼在執行期擺出來），
/// 所以移植時「重建場景」其實就是重建這幾個根節點 —— 用程式建比手拉可靠，
/// 也方便之後每個場景照抄一份。
///
/// 用法：Unity 選單 → Witch Shop → 建立切片測試場景
/// </summary>
public static class SpikeSceneBuilder
{
    /// <summary>
    /// 設計解析度 960×640（沿用 Cocos 版的 fitHeight）。
    /// PPU = 1 ⇒ 正交攝影機的 size ＝ 畫面高的一半。
    /// </summary>
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立切片測試場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ── 攝影機 ──────────────────────────────────────────────
        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;      // PPU=1 → 半個畫面高
        cam.backgroundColor = new Color32(0x2E, 0x3A, 0x2A, 0xFF);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";

        // ── World / Ground ─────────────────────────────────────
        var world = new GameObject("World");
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var groundSr = ground.AddComponent<SpriteRenderer>();
        groundSr.sprite = LoadSprite("art/ground-grass");
        groundSr.sortingOrder = -100;
        // 草地是一小張可平鋪的圖 → 拉成一整片地板，PlayerController 會照它算邊界
        groundSr.drawMode = SpriteDrawMode.Tiled;
        groundSr.size = new Vector2(2816f, 1792f);     // ＝ PlayerController 預設半寬/半高 ×2

        // ── Props / Player ─────────────────────────────────────
        var props = new GameObject("Props");
        var player = new GameObject("Player");
        player.transform.SetParent(props.transform);
        player.transform.position = Vector3.zero;
        var psr = player.AddComponent<SpriteRenderer>();
        psr.sortingOrder = 10;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";                          // 切片只有一個場景，先不換場

        Selection.activeGameObject = player;

        const string path = "Assets/Scenes/Spike.unity";
        System.IO.Directory.CreateDirectory("Assets/Scenes");
        EditorSceneManager.SaveScene(scene, path);
        Debug.Log($"[SpikeSceneBuilder] 建好了：{path}\n" +
                  "按 Play → WASD/方向鍵走路、Shift 衝刺、J 或空白鍵施法、點地面自動走過去。");
    }

    /// <summary>
    /// 載入要**存進場景**的 Sprite。
    ///
    /// ⚠️ 這裡一定要 Resources.Load&lt;Sprite&gt;，不能學 GameArt 用 Sprite.Create 現切 ——
    ///    Sprite.Create 生出來的是執行期物件、不是資產，存進場景檔後沒有 GUID 可以指，
    ///    重開場景就變成一個看不出原因的 null（畫面上地面直接消失）。
    ///    GameArt 那邊是執行期用完即丟，所以現切沒問題；編輯器端存檔的就不行。
    ///
    ///    Sprite 子資產是 PixelArtImporter 把 textureType 設成 Sprite 之後 Unity 自動產生的，
    ///    PPU 也已經是 1，跟 SheetSlicer 的設定一致。
    /// </summary>
    static Sprite LoadSprite(string resourcePath)
    {
        var sp = Resources.Load<Sprite>(resourcePath);
        if (sp == null) Debug.LogWarning($"[SpikeSceneBuilder] 找不到 {resourcePath}");
        return sp;
    }
}
