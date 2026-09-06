using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;
using WitchShop.Data;

/// <summary>
/// 從 ForestLayout 蓋出森林場景（對應 Cocos 的 main.scene）。
///
/// 原本這 84 個採集點是在 Cocos 編輯器裡一個一個擺的。座標與每個點的產出設定
/// 已經被轉換器抽進 ForestLayout.cs，這裡照著擺回去 —— 地貌跟原版一模一樣。
///
/// 用法：選單 Witch Shop → 建立森林場景
/// </summary>
public static class ForestSceneBuilder
{
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立森林場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ── 攝影機 ──────────────────────────────────────────────
        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;     // PPU=1 → 半個畫面高
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x2E, 0x3A, 0x2A, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        camGo.AddComponent<CameraFollow>();           // 跟著女巫跑

        // ── World / Ground ─────────────────────────────────────
        var world = new GameObject("World");
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var gsr = ground.AddComponent<SpriteRenderer>();
        gsr.sprite = SceneBuildUtil.LoadSprite(ForestLayout.GroundArt);
        gsr.sortingOrder = -10000;
        gsr.drawMode = SpriteDrawMode.Tiled;
        gsr.size = ForestLayout.GroundSize;           // 2816×1792，＝可走範圍

        // ── 採集點 ──────────────────────────────────────────────
        var spots = new GameObject("Spots");
        spots.transform.SetParent(world.transform);
        int made = 0, missing = 0;
        foreach (var s in ForestLayout.Spots)
        {
            var go = SceneBuildUtil.MakeSprite(s.Art, s.X, s.Y, s.Scale, spots.transform);
            if (go == null) { missing++; continue; }
            var g = go.AddComponent<GatherTree>();
            g.itemName = s.Item;
            g.gatherRange = s.Range;
            g.cooldown = s.Cooldown;
            g.minYield = s.MinYield;
            g.maxYield = s.MaxYield;
            g.rareItem = s.RareItem;
            g.rareChance = s.RareChance;
            made++;
        }

        // ── 純裝飾 ──────────────────────────────────────────────
        var props = new GameObject("Props");
        props.transform.SetParent(world.transform);
        foreach (var p in ForestLayout.Props)
            if (SceneBuildUtil.MakeSprite(p.Art, p.X, p.Y, p.Scale, props.transform) == null) missing++;

        // ── 女巫 ────────────────────────────────────────────────
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = Vector3.zero;
        var psr = player.AddComponent<SpriteRenderer>();
        psr.sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";                          // 換場交給 Data.Portals（森林東→城鎮、北→糖果鎮）

        cam.GetComponent<CameraFollow>().target = player.transform;
        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/main.unity";   // ⚠️ 沿用 Cocos 的場景名
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);   // 沒登記進 Build Settings 就 LoadScene 不到

        Debug.Log($"[ForestSceneBuilder] 建好了：{path}\n" +
                  $"採集點 {made} 個、裝飾 {ForestLayout.Props.Length} 個" +
                  (missing > 0 ? $"（{missing} 個找不到圖）" : "") + "\n" +
                  "按 Play → WASD 走路、走近樹按 E 採集、B 開背包。");
    }
}
