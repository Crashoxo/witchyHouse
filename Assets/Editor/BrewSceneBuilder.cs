using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WitchShop.Core;

/// <summary>
/// 蓋出藥水室場景（對應 Cocos 的 brew.scene）。
///
/// 原場景 9 個節點，內容（背景/鍋爐/床/倉庫/門）全部由 BrewRoom 在執行期生出來，
/// 所以這裡只放攝影機與女巫。
///
/// 用法：選單 Witch Shop -> 建立藥水室場景
/// </summary>
public static class BrewSceneBuilder
{
    const float DesignHeight = 640f;

    [MenuItem("Witch Shop/建立藥水室場景")]
    public static void Build()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera");
        var cam = camGo.AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = DesignHeight / 2f;
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color32(0x18, 0x14, 0x1E, 0xFF);
        cam.transform.position = new Vector3(0f, 0f, -100f);
        camGo.tag = "MainCamera";
        camGo.AddComponent<CameraFollow>();

        var world = new GameObject("World");

        // 背景由 BrewRoom 執行期貼（日夜兩張），這裡放一個量可走範圍用的 Ground
        var ground = new GameObject("Ground");
        ground.transform.SetParent(world.transform);
        var gsr = ground.AddComponent<SpriteRenderer>();
        gsr.sprite = SceneBuildUtil.LoadSprite("rooms/brew-room-day");
        gsr.sortingOrder = -10001;
        gsr.enabled = false;   // 只當尺寸來源，畫面由 BrewRoom 負責

        // 女巫出生點：離出口 (0,-330) 80px。SceneDoor 的 armed 機制會擋住
        // 「一載入就被門彈回去」的無限來回。
        var player = new GameObject("Player");
        player.transform.SetParent(world.transform);
        player.transform.position = new Vector3(0f, -250f, 0f);
        player.AddComponent<SpriteRenderer>().sortingOrder = 0;
        player.AddComponent<CharacterAnimator>();
        var pc = player.AddComponent<PlayerController>();
        pc.nextMapScene = "";

        cam.GetComponent<CameraFollow>().target = player.transform;
        Selection.activeGameObject = player;

        System.IO.Directory.CreateDirectory("Assets/Scenes");
        const string path = "Assets/Scenes/brew.unity";
        EditorSceneManager.SaveScene(scene, path);
        SceneBuildUtil.Register(path);

        Debug.Log("[BrewSceneBuilder] 建好了：" + path + "\n" +
                  "按 Play -> 走到鍋爐前按 E 調藥水、床按 E 睡覺、左邊木箱按 E 開倉庫。");
    }
}
