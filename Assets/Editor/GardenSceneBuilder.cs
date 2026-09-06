using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;
using WitchShop.Data;

/// <summary>
/// 蓋出後花園場景（對應 Cocos 的 garden.scene）。
///
/// 原場景只有 7 個節點 —— 背景、可走範圍、玩家。花圃、回店的門、柵欄外的村民
/// 全部是執行期由 GardenRoom 生出來的，所以這裡建的場景也很空。
///
/// 用法：選單 Witch Shop → 建立後花園場景
/// </summary>
public static class GardenSceneBuilder
{
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立後花園場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x24, 0x30, 0x24, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        camGo.AddComponent<CameraFollow>();      // 背景 1376×768 比畫面大，要跟隨

        var world = new GameObject("World");

        // 背景由 GardenRoom 在執行期貼（rooms/garden），這裡只放一個量尺寸用的 Ground
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var gsr = ground.AddComponent<SpriteRenderer>();
        gsr.sprite = SceneBuildUtil.LoadSprite("rooms/garden");
        gsr.sortingOrder = -10001;

        // ⚠️ WalkArea：草地是個菱形，可以走的範圍比整張背景（1376×768）小很多 ——
        //    沒有它人會走到柵欄外的石板路和房子上面去。尺寸與位置抄自原場景。
        //    PlayerController.ComputeBounds() 會優先採用名叫 WalkArea 的物件。
        var walk = new GameObject("WalkArea");
        walk.transform.SetParent(world.transform);
        walk.transform.position = new Vector3(30f, -30f, 0f);
        var wsr = walk.AddComponent<SpriteRenderer>();
        wsr.sprite = SceneBuildUtil.LoadSprite("rooms/garden");   // 只借它量尺寸
        wsr.drawMode = SpriteDrawMode.Sliced;
        wsr.size = new Vector2(800f, 440f);
        wsr.enabled = false;                                      // 純粹當範圍用，不畫出來

        // 女巫：出生在回店裡那道門旁邊（但要離門夠遠，不然一進來就被彈回去 ——
        // SceneDoor 的 armed 機制也會擋，這裡再拉開一點比較保險）
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = new Vector3(250f, 55f, 0f);
        player.AddComponent<SpriteRenderer>().sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";        // 出去要走地板上的門，不是邊界

        cam.GetComponent<CameraFollow>().target = player.transform;
        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/garden.unity";
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);

        Debug.Log($"[GardenSceneBuilder] 建好了：{path}\n" +
                  $"花圃 {Garden.UnlockedCount()} 塊（其餘要在店裡升級「花圃」才開得出來）\n" +
                  "按 Play → 走到花圃旁按 E：空地種種子、有花澆水、開花了收成。");
    }
}
