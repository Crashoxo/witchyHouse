using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 糖果鎮：森林北邊那張地圖。地面、建築、裝飾、三位 NPC、街上晃來晃去的
    /// 軟糖鱷與薑餅人，全部依 Data.Candy 生出來。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版的 CandyTown.ts 幾乎什麼都不做（只把商品清單交給場景裡的商店節點），
    /// 因為地圖與房子**都是 candy.scene 裡的真節點** —— 使用者要能在 Cocos 編輯器裡
    /// 自己拖。這邊沒有那個場景檔，但 Data.Candy 裡的座標是完整的（那份資料本來就是
    /// 早期用來生成的），所以改成全部由這支生出來，結果一樣。
    ///
    /// 進出是「走到地圖邊界」：森林北側 → 糖果鎮、糖果鎮南側 → 森林，
    /// 兩邊都登記在 Data.Portals，PortalGlow 會在那個點畫光圈。
    /// </summary>
    public class CandyTown : MonoBehaviour
    {
        public static CandyTown Instance { get; private set; }

        public static CandyTown Ensure()
        {
            if (Instance != null) return Instance;
            return new GameObject("CandyTown").AddComponent<CandyTown>();
        }

        /// <summary>⚠️ NPC 與建築的圖在 art/candy/（不是 candy/）—— 那批在 Cocos 是場景節點用的。</summary>
        const string ArtDir = "art/candy/";

        /// <summary>同時最多幾隻街上晃的小動物。</summary>
        const int CritterCount = 6;

        class Walker
        {
            public GameObject Node;
            public Vector2 Target;
            public float Speed;
            public float Pause;
            public SpriteRenderer Sr;
        }

        readonly List<Walker> critters = new();

        void Awake() { Instance = this; GameArt.Preload(); }
        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start()
        {
            GameArt.OnReady(Build);
        }

        void Build()
        {
            SpawnProps();
            SpawnNpcs();
            SpawnCritters();
        }

        // ──────────── 建築與裝飾 ────────────

        void SpawnProps()
        {
            var buildings = new GameObject("Buildings");
            buildings.transform.SetParent(transform);
            foreach (var b in Candy.Buildings)
                Place(b.Art, b.X, b.Y, b.Scale, buildings.transform);

            var props = new GameObject("Props");
            props.transform.SetParent(transform);
            foreach (var p in Candy.Props)
                Place(p.Art, p.X, p.Y, p.Scale, props.transform);
        }

        /// <summary>
        /// 擺一張圖，錨點在腳底（跟村民、家具同一套）—— position 就是「站在地上那一點」，
        /// YSort 才排得對。
        /// </summary>
        GameObject Place(string art, float x, float y, float scale, Transform parent)
        {
            var sp = Resources.Load<Sprite>(ArtDir + art);
            if (sp == null) { Debug.LogWarning($"[CandyTown] 找不到 {ArtDir}{art}"); return null; }

            var go = new GameObject(art);
            go.transform.SetParent(parent);
            go.transform.position = new Vector3(x, y, 0f);

            var artGo = new GameObject("art");
            artGo.transform.SetParent(go.transform, false);
            artGo.transform.localScale = new Vector3(scale, scale, 1f);
            artGo.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * scale, 0f);

            var sr = artGo.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = Mathf.RoundToInt(-y);
            return go;
        }

        // ──────────── NPC ────────────

        void SpawnNpcs()
        {
            var box = new GameObject("Npcs");
            box.transform.SetParent(transform);

            foreach (var n in Candy.Npcs)
            {
                var go = Place(n.Art, n.X, n.Y, n.Scale, box.transform);
                if (go == null) continue;
                go.name = n.Id;

                var talk = go.AddComponent<TalkNpc>();
                talk.npcName = n.Name;
                talk.lines = n.Lines;
                talk.portrait = "";              // 糖果鎮的角色沒有頭像立繪
                talk.interactRange = 200f;
                // 有店名的就兼賣東西：聊完會問「要看看貨嗎」（見 TalkNpc.shopTitle 的說明，
                // 刻意不做成第二個按 E 的觸發點，那樣兩個感應圈會搶同一顆 E）
                talk.shopTitle = n.ShopTitle ?? "";
            }
        }

        // ──────────── 街上晃來晃去的小動物 ────────────

        void SpawnCritters()
        {
            var box = new GameObject("Critters");
            box.transform.SetParent(transform);

            for (int i = 0; i < CritterCount && i < Candy.Critters.Length; i++)
            {
                var c = Candy.Critters[i];
                var sp = GameArt.CandyArt(c.Art);
                if (sp == null) continue;

                var start = PickWaypoint();
                var go = new GameObject("critter-" + c.Art);
                go.transform.SetParent(box.transform);
                go.transform.position = new Vector3(start.x, start.y, 0f);

                var artGo = new GameObject("art");
                artGo.transform.SetParent(go.transform, false);
                artGo.transform.localScale = new Vector3(c.Scale, c.Scale, 1f);
                artGo.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * c.Scale, 0f);
                var sr = artGo.AddComponent<SpriteRenderer>();
                sr.sprite = sp;

                // 腳下的影子（go 的 position 就是落腳點）
                ShadowLayer.Follow(go.transform, sp.rect.width * c.Scale);

                critters.Add(new Walker
                {
                    Node = go, Sr = sr,
                    Target = PickWaypoint(),
                    Speed = 34f + Random.value * 26f,
                    Pause = Random.value * 3f,
                });
            }
        }

        static Vector2 PickWaypoint()
        {
            var p = Candy.Walk[Random.Range(0, Candy.Walk.Length)];
            return new Vector2(p.x + (Random.value - 0.5f) * 120f,
                               p.y + (Random.value - 0.5f) * 80f);
        }

        void Update()
        {
            if (UIState.ModalOpen) return;
            float dt = Time.deltaTime;

            foreach (var w in critters)
            {
                if (w.Node == null) continue;

                // YSort：站得低的畫在前面
                w.Sr.sortingOrder = Mathf.RoundToInt(-w.Node.transform.position.y);

                if (w.Pause > 0f) { w.Pause -= dt; continue; }

                var p = w.Node.transform.position;
                float dx = w.Target.x - p.x, dy = w.Target.y - p.y;
                float dist = Mathf.Sqrt(dx * dx + dy * dy);
                float step = w.Speed * dt;

                if (dist <= step)
                {
                    w.Node.transform.position = new Vector3(w.Target.x, w.Target.y, 0f);
                    w.Target = PickWaypoint();
                    w.Pause = 1.5f + Random.value * 3f;
                    continue;
                }

                w.Node.transform.position =
                    new Vector3(p.x + dx / dist * step, p.y + dy / dist * step, 0f);
                // 往右走就翻面（這批圖畫的都是朝左）
                var s = w.Node.transform.localScale;
                float want = dx > 0 ? -Mathf.Abs(s.x) : Mathf.Abs(s.x);
                if (!Mathf.Approximately(want, s.x))
                    w.Node.transform.localScale = new Vector3(want, s.y, s.z);
            }
        }
    }
}
