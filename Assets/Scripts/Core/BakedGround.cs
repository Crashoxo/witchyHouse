using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace WitchShop.Core
{
    /// <summary>
    /// 戶外地圖的地面換成「烤好的像素地面」（森林 main／城鎮 town／糖果鎮 candy）。
    ///
    /// 地面圖由離線工具 tools/bake_ground.py 產生（見 tools/ground/README.md），存在
    /// Resources/art/ground/&lt;forest|town|candy&gt;.png，**解析度是世界大小的一半**：
    /// 1 個美術像素 ＝ <see cref="ArtPixel"/> 個世界像素。這裡用 PPU = 1/ArtPixel 建 Sprite
    /// 貼回場景裡既有的 Ground，所以：
    ///   - 世界大小與原本完全一樣（2816×1792 / 3200×2048），可走範圍、攝影機邊界、
    ///     邊界傳送點全部不受影響 —— 換之前比對大小、換之後再驗一次中心與大小，
    ///     對不上就不換（或還原）、留原圖；
    ///   - 像素格子是銳利的方塊。原本 3200 寬的整張圖會被匯入設定的 Max Size 2048
    ///     縮小再拉回來，格子會糊、會大小不一；半解析度的圖 1600 寬，原尺寸匯入。
    ///
    /// ⚠️ 不改場景檔、不改 PlayerController：遊戲啟動時自己掛上 sceneLoaded，
    ///    場景一載入（Awake 之後、Start 之前）就把 Ground 的圖換掉。
    ///    場景裡原本那張（ground-grass / town-ground / candy-town）只剩編輯器裡看的作用，
    ///    內容也是同一份烘焙結果的放大版，所以編輯器裡看到的跟遊戲裡一樣。
    ///
    /// 排序不動：Ground 仍是 -10000（傳送點光圈 -9000、角色影子 -8500 都在它之上）。
    /// </summary>
    public static class BakedGround
    {
        /// <summary>一個美術像素佔幾個世界像素（要跟 tools/ground/common.py 的 ART_PX 一致）。</summary>
        public const float ArtPixel = 2f;

        static readonly Dictionary<string, Sprite> cache = new();

        /// <summary>場景名 → Resources 路徑。只有這三張戶外地圖有烤好的地面。</summary>
        static string ArtFor(string scene) => scene switch
        {
            "main" => "art/ground/forest",
            "town" => "art/ground/town",
            "candy" => "art/ground/candy",
            _ => null,
        };

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Hook()
        {
            // 先拿掉再掛：關掉 Domain Reload 時靜態事件會殘留，避免重複掛
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode) => Apply(scene);

        /// <summary>把這個場景的 Ground 換成烤好的地面（沒有對應的圖、或大小對不上就什麼都不做）。</summary>
        public static void Apply(Scene scene)
        {
            string path = ArtFor(scene.name);
            if (path == null) return;

            var sr = FindGround(scene);
            if (sr == null) return;

            var sp = Load(path);
            if (sp == null) return;

            // 大小一定要跟原本的 Ground 一樣：可走範圍、攝影機、邊界傳送點都是量它算的
            var t = sr.transform;
            Bounds before = sr.bounds;
            Vector2 got = Vector2.Scale(sp.bounds.size, t.lossyScale);
            if (!Near(before.size, got))
            {
                Debug.LogWarning($"[BakedGround] {path} 是 {got}，場景的 Ground 是 {before.size}，大小對不上 —— 不換，沿用原圖。" +
                                 "（重跑 tools/bake_ground.py？）");
                return;
            }

            // 記下原狀，換壞了可以整組還原
            var oldSprite = sr.sprite;
            var oldMode = sr.drawMode;
            var oldSize = sr.size;
            var oldScale = t.localScale;

            // ⚠️ 不要切 drawMode。森林的 Ground 是 Tiled（256 的磚、size 2816×1792），曾經在這裡改成
            //    Simple 再換圖 —— 結果地面被放大 11×7 倍（每個美術像素變成約 22×14 的大方塊）：
            //    推測是 Unity 切 drawMode 時為了「畫面上大小不變」把 size 換算進 transform 的 localScale
            //    （2816/256＝11、1792/256＝7；倍數完全吻合，但沒在實機逐步確認），新圖本身已經是
            //    2816×1792，就被再放大一次。下面的做法不管真正原因是哪個都成立：不切 drawMode、
            //    明確設 size、還原 scale，最後再驗 bounds。
            //    改成維持原本的 drawMode：Tiled/Sliced 就把 size 設成新圖的大小（新圖是 FullRect，
            //    剛好鋪一格＝整張）；Simple（城鎮、糖果鎮）照舊只換 sprite。localScale 一律還原。
            sr.sprite = sp;
            if (oldMode != SpriteDrawMode.Simple) sr.size = sp.bounds.size;
            t.localScale = oldScale;

            // 換完再驗一次：中心與大小都要跟換圖前一樣，不一樣就整組還原（寧可顯示舊地面也不要錯的）
            Bounds after = sr.bounds;
            if (!Near(before.size, after.size) || !Near(before.center, after.center))
            {
                sr.sprite = oldSprite;
                sr.drawMode = oldMode;
                sr.size = oldSize;
                t.localScale = oldScale;
                Debug.LogWarning($"[BakedGround] 換上 {path} 後 Ground 變成 {after.center}/{after.size}" +
                                 $"（原本 {before.center}/{before.size}）—— 已還原成原圖。");
            }
        }

        /// <summary>兩個大小/位置差在 1 像素以內。</summary>
        static bool Near(Vector2 a, Vector2 b) => Mathf.Abs(a.x - b.x) <= 1f && Mathf.Abs(a.y - b.y) <= 1f;

        static Sprite Load(string path)
        {
            // ⚠️ 用 Unity 的 null 判斷：換場景時 Resources.UnloadUnusedAssets 可能把它收掉
            if (cache.TryGetValue(path, out var sp) && sp != null) return sp;

            var tex = Resources.Load<Texture2D>(path);
            if (tex == null) { Debug.LogWarning($"[BakedGround] 找不到 {path}"); return null; }
            tex.filterMode = FilterMode.Point;        // 匯入設定已經是 Point，保險再設一次
            sp = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f),
                               1f / ArtPixel, 0, SpriteMeshType.FullRect);
            sp.name = System.IO.Path.GetFileName(path) + "-baked";
            cache[path] = sp;
            return sp;
        }

        /// <summary>找這個場景裡名叫 Ground 的 SpriteRenderer（通常在 World/Ground）。</summary>
        static SpriteRenderer FindGround(Scene scene)
        {
            foreach (var root in scene.GetRootGameObjects())
            {
                var t = root.name == "Ground" ? root.transform : FindChild(root.transform, "Ground");
                if (t != null && t.TryGetComponent<SpriteRenderer>(out var sr)) return sr;
            }
            return null;
        }

        static Transform FindChild(Transform t, string name)
        {
            for (int i = 0; i < t.childCount; i++)
            {
                var c = t.GetChild(i);
                if (c.name == name) return c;
                var hit = FindChild(c, name);
                if (hit != null) return hit;
            }
            return null;
        }
    }
}
