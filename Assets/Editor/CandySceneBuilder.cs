using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;

/// <summary>
/// 蓋出糖果鎮場景（對應 Cocos 的 candy.scene）。
///
/// 建築、裝飾、NPC、街上的小動物都由 CandyTown 在執行期依 Data.Candy 生出來，
/// 所以這裡只放地面、攝影機與女巫。
///
/// 用法：選單 Witch Shop -> 建立糖果鎮場景
/// </summary>
public static class CandySceneBuilder
{
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立糖果鎮場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x3A, 0x2A, 0x36, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        camGo.AddComponent<CameraFollow>();

        var world = new GameObject("World");

        // 地面：一整張畫好的糖果鎮地圖（3200x2048）。不是平鋪的，所以不用 Tiled。
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var gsr = ground.AddComponent<SpriteRenderer>();
        gsr.sprite = SceneBuildUtil.LoadSprite("art/candy/candy-town");
        gsr.sortingOrder = -10000;

        // 女巫：出生在南側（往南走回森林的那個出口附近，但拉開一點免得一進來就被彈回去）
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = new Vector3(0f, -820f, 0f);
        player.AddComponent<SpriteRenderer>().sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";        // 換場交給 Data.Portals（糖果鎮南 -> 森林）

        cam.GetComponent<CameraFollow>().target = player.transform;
        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/candy.unity";
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);

        Debug.Log("[CandySceneBuilder] 建好了：" + path + "\n" +
                  "建築 7 棟、裝飾 21 個、NPC 3 位、街上小動物 6 隻 —— 都是 Play 之後才生出來的。\n" +
                  "往南走可以回森林。");
    }
}
