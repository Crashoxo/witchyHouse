using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 採集點：玩家走近、按 E 採集 → 產出材料、進入冷卻（圖變暗）、一段時間後長回來。
    ///
    /// 掛在每一個採集點上。玩家參照自動從場景裡名叫 "Player" 的物件抓，
    /// 所以 84 個採集點不用一個一個拖。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用 input.on(KEY_DOWN) 讓**每一棵樹**各自註冊一個鍵盤監聽 ——
    /// 84 棵樹＝84 個監聽器，每次按任何鍵都會全部跑一遍。
    /// Unity 這邊改成在 Update 裡輪詢（Input.GetKeyDown 本來就是輪詢式的），
    /// 而且先比距離再處理，省掉那 84 個監聽器與它們的註冊/解除。
    ///
    /// 尚未接上（原版有、這裡先留 TODO）：
    ///   Quests.Record()      採集任務進度
    ///   Toast                背包滿了的提示（先寫 Console）
    /// </summary>
    [RequireComponent(typeof(SpriteRenderer))]
    public class GatherTree : MonoBehaviour
    {
        [Tooltip("玩家離多近才採得到（像素）")] public float gatherRange = 120f;
        [Tooltip("採完幾秒後長回來")] public float cooldown = 5f;
        [Tooltip("這個點產出什麼材料")] public string itemName = "木材";
        [Tooltip("每次最少採到幾個")] public int minYield = 1;
        [Tooltip("每次最多採到幾個")] public int maxYield = 3;
        [Tooltip("額外稀有掉落的物品名（空＝沒有）")] public string rareItem = "";
        [Tooltip("掉到稀有物的機率（0~1）")] public float rareChance = 0.15f;

        /// <summary>每次採集額外撿到一包花種子的機率。</summary>
        const float SeedChance = 0.18f;

        Transform player;
        SpriteRenderer sr;
        Color original;
        bool ready = true;       // true = 可採，false = 冷卻中
        float timer;

        void Awake()
        {
            sr = GetComponent<SpriteRenderer>();
            original = sr.color;
        }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;

            // 提示與按 E 交給共用的互動系統（2026-11-28）：頭上 [E][會採到的材料圖]；採光了（冷卻中）不顯示、不吃 E。
            // ⚠️ 以前每一棵樹各自看 E —— 兩棵樹都在範圍內時一下 E 兩棵一起採；現在只有最近的那棵。
            var it = Interactable.Attach(gameObject, gatherRange, Gather,
                () => HintLook.E(HintIcons.Item(itemName) ?? HintIcons.Ui("act_done"), null));   // 以前沒有文字提示 → 開關關掉時也不顯示
            it.available = () => ready;
        }

        void Update()
        {
            if (!ready)
            {
                timer += Time.deltaTime;
                if (timer >= cooldown)
                {
                    ready = true;
                    sr.color = original;      // 長回來了
                }
                return;
            }

            // 按 E 採集改由 Interact 處理（開著視窗時不採集、範圍重疊時最近的那棵）
        }

        /// <summary>
        /// 這項材料是不是當季盛產（採量 +1、稀有掉落機率加成）。
        /// 當季材料表在 Data.Seasons，例：夏天盛產漿果/黑莓/藍莓。
        /// </summary>
        static bool InSeason(string item)
        {
            var list = TimeSystem.SeasonDef.BonusItems;
            if (list == null) return false;
            foreach (var n in list) if (n == item) return true;
            return false;
        }

        void Gather()
        {
            // 隨機數量（min~max），當季盛產的材料多給一個
            int lo = Mathf.Min(minYield, maxYield);
            int hi = Mathf.Max(minYield, maxYield);
            int qty = Random.Range(lo, hi + 1) + (InSeason(itemName) ? 1 : 0);

            // 背包裝不下（種類滿了）就直說一聲 —— 不要靜靜地把採到的東西丟掉
            if (!Inventory.Add(itemName, qty))
            {
                Sfx.Play("deny");
                UI.Toast.Show("背包滿了，先回去整理一下");
                return;
            }
            DailyLog.RecordGather(qty);
            QuestLog.Record(ObjKind.Gather, itemName, qty);

            PlayFx(itemName, qty);

            // 機率額外掉稀有物（稀有物也當季的話機率再提高）
            float rareRate = rareChance * (!string.IsNullOrEmpty(rareItem) && InSeason(rareItem) ? 1.6f : 1f);
            if (!string.IsNullOrEmpty(rareItem) && Random.value < rareRate)
            {
                Inventory.Add(rareItem, 1);
                StartCoroutine(PopLater(rareItem, 1, 46f, 0.35f));   // 慢一拍再冒，才看得出是兩件事
            }

            // 森林裡採東西時偶爾會撿到花種子 —— 後花園的種子就是這樣來的。
            // 做成掉落機率而不是逐個點去設定，才不用改場景。
            if (Random.value < SeedChance)
            {
                var f = GardenData.Flowers[Random.Range(0, GardenData.Flowers.Length)];
                Inventory.Add(f.Seed, 1);
                StartCoroutine(PopLater(f.Seed, 1, 64f, 0.6f));
            }

            ready = false;
            timer = 0f;
            sr.color = new Color32(80, 80, 80, 255);      // 變暗＝採光了
        }

        // ──────────── 採集特效 ────────────

        /// <summary>女巫伸手採集 + 樹搖晃 + 星星 + 材料飄出來。</summary>
        void PlayFx(string item, int qty)
        {
            // 女巫：轉向這個點伸手
            if (player != null)
            {
                var anim = player.GetComponent<CharacterAnimator>();
                if (anim != null)
                {
                    float dx = transform.position.x - player.position.x;
                    float dy = transform.position.y - player.position.y;
                    int dir = CharacterAnimator.DirOf(dx, dy);
                    anim.PlayOneShot(GameArt.GatherFrames(dir), 0.9f, dx, false, dir);
                }
            }

            Sfx.Play("gather");                            // 樹葉沙沙
            StartCoroutine(Shake());                       // 樹左右擺
            for (int i = 0; i < 6; i++) Spark();           // 樹冠散出星星
            PopItem(item, qty, 0f);                        // 材料圖示往上冒
        }

        /// <summary>
        /// 樹**以樹根為軸**左右擺一下。
        /// 原版是 tween 串四段角度：-4° → 3.5° → -1.5° → 0°，這裡照抄那個節奏。
        ///
        /// ⚠️ Cocos 那邊樹的錨點是 (0.5, 0)＝底部中央，所以轉起來像是被風吹。
        ///    Unity 的 Sprite 樞紐在正中心（見 SheetSlicer），直接轉會變成整棵樹
        ///    在半空中打轉。所以這裡自己算：轉完之後把位置補回去，讓「底部中央」
        ///    那一點固定不動。
        /// </summary>
        System.Collections.IEnumerator Shake()
        {
            if (shaking) yield break;         // 連按時不要疊在一起轉
            shaking = true;

            var home = transform.position;
            float halfH = sr.sprite != null
                ? sr.sprite.rect.height * 0.5f * Mathf.Abs(transform.localScale.y)
                : 0f;
            var pivot = home - new Vector3(0f, halfH, 0f);      // 樹根
            var arm = home - pivot;                             // 樞紐 → 中心

            (float angle, float dur)[] steps =
                { (-4f, 0.07f), (3.5f, 0.12f), (-1.5f, 0.10f), (0f, 0.07f) };

            float from = 0f;
            foreach (var s in steps)
            {
                float t = 0f;
                while (t < s.dur)
                {
                    t += Time.deltaTime;
                    float z = Mathf.Lerp(from, s.angle, Mathf.Clamp01(t / s.dur));
                    Apply(z);
                    yield return null;
                }
                Apply(s.angle);
                from = s.angle;
            }

            transform.rotation = Quaternion.identity;
            transform.position = home;
            shaking = false;

            void Apply(float z)
            {
                var rot = Quaternion.Euler(0f, 0f, z);
                transform.rotation = rot;
                transform.position = pivot + rot * arm;         // 讓樹根留在原地
            }
        }

        bool shaking;

        /// <summary>這個採集點在世界裡的大小（圖的尺寸 × 縮放）。</summary>
        Vector2 VisualSize()
        {
            var b = sr.bounds.size;
            return new Vector2(b.x, b.y);
        }

        /// <summary>樹冠冒一顆往上飄的小星星。</summary>
        void Spark()
        {
            var size = VisualSize();
            var go = new GameObject("spark");
            go.transform.SetParent(transform.parent);
            go.transform.position = transform.position + new Vector3(
                (Random.value - 0.5f) * size.x * 0.7f,
                size.y * (0.45f + Random.value * 0.35f), 0f);

            var s = go.AddComponent<SpriteRenderer>();
            s.sprite = CircleSprite();
            s.color = new Color32(255, 240, 170, 255);
            s.sortingOrder = 9000;
            float r = 2f + Random.value * 2.5f;
            go.transform.localScale = new Vector3(r, r, 1f);

            go.AddComponent<FloatAway>().Begin(
                new Vector3((Random.value - 0.5f) * 40f, 34f + Random.value * 26f, 0f),
                0.5f + Random.value * 0.3f, 0.35f);
        }

        /// <summary>延遲一下再冒（稀有掉落與種子用，跟主要材料錯開才看得出是兩件事）。</summary>
        System.Collections.IEnumerator PopLater(string item, int qty, float extraY, float delay)
        {
            yield return new WaitForSeconds(delay);
            PopItem(item, qty, extraY);
        }

        /// <summary>採到的材料：圖示＋數量從樹上飄出來、往上淡出。</summary>
        void PopItem(string item, int qty, float extraY)
        {
            // 東西冒出來＝拿到了。稀有掉落／種子是慢一拍才冒的，聲音也跟著慢一拍。
            Sfx.Play("pickup", 0.85f);

            var size = VisualSize();
            var go = new GameObject("pop");
            go.transform.SetParent(transform.parent);
            go.transform.position = transform.position + new Vector3(0f, size.y * 0.62f + extraY, 0f);

            var frame = GameArt.Item(item);
            if (frame != null)
            {
                var icon = new GameObject("icon");
                icon.transform.SetParent(go.transform);
                icon.transform.localPosition = new Vector3(-16f, 0f, 0f);
                var isr = icon.AddComponent<SpriteRenderer>();
                isr.sprite = frame;
                isr.sortingOrder = 9001;
                // 縮到最長邊 34px（原版同樣的算法）。
                // ⚠️ 8-bit 道具圖（GameArt.UsePixelItems）四周留了透明邊、圖案只佔約 80%，
                //    所以經 ItemIconWorld 換成 40px，東西本身才跟舊圖一樣約 34px 大。
                float k = GameArt.ItemIconWorld(34f) / Mathf.Max(frame.rect.width, frame.rect.height);
                icon.transform.localScale = new Vector3(k, k, 1f);
            }

            MakeText(go.transform, frame != null ? $"×{qty}" : $"{item} ×{qty}",
                     new Vector3(frame != null ? 16f : 0f, 0f, 0f));

            go.AddComponent<FloatAway>().Begin(new Vector3(0f, 52f, 0f), 0.9f, 0.5f);
        }

        /// <summary>
        /// 世界空間的文字。
        ///
        /// ⚠️ 用 TextMesh 而不是 TextMeshPro：TextMesh 吃得下「作業系統的動態字型」，
        ///    所以中文（材料名）不用先做 FontAsset 就能顯示。TMP 要先烘一份含中日韓字的
        ///    FontAsset，那是出版階段才要處理的事（見 CjkFont 的說明）。
        ///
        /// ⚠️ TextMesh 的世界大小 ≈ fontSize × characterSize ÷ 10。這裡要約 22px 高的字，
        ///    所以 44 × 5 ÷ 10 = 22。字看起來太大或太小的話就調 CharSize。
        /// </summary>
        const int TextFontSize = 44;
        const float CharSize = 5f;

        static void MakeText(Transform parent, string str, Vector3 localPos)
        {
            var font = UI.CjkFont.Get();

            // 先畫一份深色的當描邊（TextMesh 沒有 outline，錯開一點點疊在後面）
            for (int pass = 0; pass < 2; pass++)
            {
                bool shadow = pass == 0;
                var go = new GameObject(shadow ? "text-shadow" : "text");
                go.transform.SetParent(parent);
                go.transform.localPosition = localPos + (shadow ? new Vector3(1.5f, -1.5f, 0.01f) : Vector3.zero);

                var tm = go.AddComponent<TextMesh>();
                tm.text = str;
                tm.fontSize = TextFontSize;
                tm.characterSize = CharSize;
                tm.anchor = TextAnchor.MiddleCenter;
                tm.alignment = TextAlignment.Center;
                tm.color = shadow ? new Color32(60, 40, 30, 220) : new Color32(255, 246, 214, 255);
                if (font != null)
                {
                    tm.font = font;
                    go.GetComponent<MeshRenderer>().material = font.material;
                }
                var mr = go.GetComponent<MeshRenderer>();
                mr.sortingOrder = shadow ? 9001 : 9002;
            }
        }

        /// <summary>星星用的小圓點圖（程式生成，不用另外準備素材）。</summary>
        static Sprite circle;

        static Sprite CircleSprite()
        {
            if (circle != null) return circle;
            const int N = 16;
            var tex = new Texture2D(N, N, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            float c = (N - 1) / 2f;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(c, c)) / c;
                    float a = Mathf.Clamp01(1f - d);          // 中心不透明、邊緣淡出
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a * a));
                }
            tex.Apply();
            circle = Sprite.Create(tex, new Rect(0, 0, N, N), new Vector2(0.5f, 0.5f), N);
            return circle;
        }
    }
}
