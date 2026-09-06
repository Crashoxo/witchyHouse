using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;
using WitchShop.Data;

/// <summary>
/// 蓋出商店場景（對應 Cocos 的 shop.scene）。
///
/// ⚠️ 商店跟森林/城鎮**做法完全不同**：那兩個是把手擺的座標抽出來重擺，
///    商店在 Cocos 那邊只有 9 個節點 —— 地板底圖、家具、裝飾全部是執行期
///    由 ShopRoomView 依 RoomLayout / DecorCatalog 的存檔算出來的。
///    所以這裡建的場景很空，東西是 Play 之後才長出來的。
///
/// 房間是 960×640，剛好一個畫面，所以攝影機固定不跟隨。
///
/// 用法：選單 Witch Shop → 建立商店場景
/// </summary>
public static class ShopSceneBuilder
{
    [MenuItem("Witch Shop/建立商店場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // ── 攝影機（固定，房間剛好一個畫面）──────────────────────
        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = ShopRoom.RoomH / 2f;      // 320，PPU=1
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x1A, 0x16, 0x14, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        // 刻意不加 CameraFollow —— 房間就是一個畫面大，跟隨反而會晃

        var world = new GameObject("World");

        // ── 女巫 ────────────────────────────────────────────────
        // 出生點用格座標換算（ShopRoom.PlayerSpawn = 6,5）
        var spawn = ShopRoom.TileCenter(ShopRoom.PlayerSpawn.gx, ShopRoom.PlayerSpawn.gy);
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = new Vector3(spawn.x, spawn.y, 0f);
        player.AddComponent<SpriteRenderer>().sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";        // 店裡沒有邊界出口，出去要走地板上的門（見 ShopRoom.Door*）
        pc.clampToBounds = false;    // 改用 ShopRoom.ClampToFloor 的菱形夾取

        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/shop.unity";   // ⚠️ 沿用 Cocos 的場景名
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);

        Debug.Log($"[ShopSceneBuilder] 建好了：{path}\n" +
                  "場景本身很空是正常的 —— 地板與家具是 Play 之後由 ShopRoomView 生出來的。\n" +
                  "按 Play → 應該看到店內底圖與一張販售桌，走動會被夾在菱形地板內。");
    }
}
