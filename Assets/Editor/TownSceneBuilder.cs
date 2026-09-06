using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;
using WitchShop.Data;

/// <summary>
/// 從 TownLayout 蓋出城鎮場景（對應 Cocos 的 town.scene）。
///
/// 城鎮跟森林同一個模式：71 個擺設（六間店、灌木、路燈、圍籬、橋）都是手擺的，
/// 座標已由轉換器抽進 TownLayout.cs。街上走動的村民不在場景裡 ——
/// 由 PlayerController 進 town 場景時呼叫 TownFolk.Ensure() 生出來。
///
/// 用法：選單 Witch Shop → 建立城鎮場景
/// </summary>
public static class TownSceneBuilder
{
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立城鎮場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ── 攝影機 ──────────────────────────────────────────────
        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x2A, 0x30, 0x3A, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        camGo.AddComponent<CameraFollow>();

        // ── World / Ground ─────────────────────────────────────
        // ⚠️ 城鎮的路面是**烤進 town-ground.png** 的（原專案用一張 50×32 的小地圖生成），
        //    所以地面不是平鋪的草皮，而是一整張畫好的圖 —— 這裡不能用 Tiled 模式。
        var world = new GameObject("World");
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var gsr = ground.AddComponent<SpriteRenderer>();
        gsr.sprite = SceneBuildUtil.LoadSprite(TownLayout.GroundArt);
        gsr.sortingOrder = -10000;

        // ── 擺設（建築 + 裝飾）──────────────────────────────────
        var props = new GameObject("Props");
        props.transform.SetParent(world.transform);
        int made = 0, missing = 0;
        foreach (var p in TownLayout.Props)
        {
            if (SceneBuildUtil.MakeSprite(p.Art, p.X, p.Y, p.Scale, props.transform) == null) missing++;
            else made++;
        }

        // ── 女巫 ────────────────────────────────────────────────
        // 出生點對準往西的泥土路（Portals 裡 town→main 的門也在 y=-40），
        // 這樣從森林走過來、要走回去都在同一條路上。
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = new Vector3(-1200f, -40f, 0f);
        player.AddComponent<SpriteRenderer>().sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";                    // 換場交給 Data.Portals（城鎮西 → 森林）

        cam.GetComponent<CameraFollow>().target = player.transform;
        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/town.unity";   // ⚠️ 沿用 Cocos 的場景名
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);

        Debug.Log($"[TownSceneBuilder] 建好了：{path}\n" +
                  $"擺設 {made} 個" + (missing > 0 ? $"（{missing} 個找不到圖）" : "") + "\n" +
                  "按 Play → 街上會慢慢出現走動的村民（最多 6 位）。往西走可以回森林。");
    }
}
