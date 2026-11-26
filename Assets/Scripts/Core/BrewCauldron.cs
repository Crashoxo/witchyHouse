using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 藥水室的鍋爐：走近按 E 開配方面板，選好之後在這裡演熬煮動畫、時間到產出藥水。
    ///
    /// ⚠️ 材料是**開始熬的時候就扣**（Consume），成品在動畫結束才進背包（Produce）——
    ///    這樣熬到一半跑走也不會憑空多出材料，而且畫面上「正在熬」是有代價的。
    /// </summary>
    public class BrewCauldron : MonoBehaviour
    {
        public static BrewCauldron Instance { get; private set; }

        [Tooltip("玩家離多近才能按 E")] public float interactRange = 200f;

        /// <summary>
        /// 顯示縮放。
        /// ⚠️ 原圖 224×343，Cocos 場景裡的 UITransform 是 123×189 —— 它一直是被縮到
        ///    0.55 顯示的。不套這個縮放會大將近一倍。
        /// </summary>
        public float artScale = 123f / 224f;

        SpriteRenderer sr;
        Transform art;                 // 掛 SpriteRenderer 的子物件（腳底錨點用）
        bool footPivot;                // 新房間的圖：樞紐已經在落腳點，不用再往上推
        Sprite[] frames = System.Array.Empty<Sprite>();
        Transform player;
        GameObject hint;

        bool brewing;
        Recipe pending;
        int pendingQty;
        float timer;

        void Awake()
        {
            Instance = this;
            // ⚠️ Cocos 那邊鍋爐的錨點是 (0.5, 0)＝腳底，Unity 的 Sprite 樞紐在正中心。
            //    所以圖掛在子物件上、往上推半個身高 —— 父物件的 position 才是「站在地上
            //    的那一點」，YSort 也才排得對。同 VillagerAnim / ShopRoomView 的作法。
            var go = new GameObject("art");
            art = go.transform;
            art.SetParent(transform, false);
            art.localScale = new Vector3(artScale, artScale, 1f);
            sr = go.AddComponent<SpriteRenderer>();
            sr.sortingOrder = Mathf.RoundToInt(-transform.position.y);

            GameArt.Preload();
            GameArt.OnReady(() => { frames = GameArt.CauldronFrames(); ShowFrame(0); });
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>
        /// 換成 SVG 重畫的房間那組圖（BrewRoom.UseSvgRoom）：圖的樞紐已經放在落腳點、1:1 不縮放，
        /// 排序由房間的配置表給（女巫的前後由 BrewRoom.PlayerOrder 插進來）。幀數跟舊圖一樣，播放邏輯不變。
        /// </summary>
        public void UseRoomArt(Sprite[] roomFrames, int sortingOrder)
        {
            footPivot = true;
            artScale = 1f;
            art.localScale = Vector3.one;
            art.localPosition = Vector3.zero;
            sr.sortingOrder = sortingOrder;
            frames = roomFrames ?? System.Array.Empty<Sprite>();
            ShowFrame(0);
        }

        /// <summary>夜晚的色調（房間整體乘的顏色）。</summary>
        public void SetTint(Color c) { if (sr != null) sr.color = c; }

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            BuildHint();
        }

        void ShowFrame(int i)
        {
            if (sr == null || frames.Length == 0) return;
            var f = frames[Mathf.Clamp(i, 0, frames.Length - 1)];
            sr.sprite = f;
            // 腳底錨點：圖往上推半個顯示高度（每幀尺寸一樣，但第一次要算對）
            if (f != null)
                art.localPosition = footPivot ? Vector3.zero : new Vector3(0f, f.rect.height * 0.5f * artScale, 0f);
        }

        bool InRange =>
            player != null && Vector2.Distance(player.position, transform.position) <= interactRange;

        void Update()
        {
            bool canOpen = InRange && !UIState.ModalOpen && !brewing;
            if (hint != null) hint.SetActive(canOpen);

            if (canOpen && Input.GetKeyDown(KeyCode.E))
                UI.BrewPanel.Ensure().Open(this);

            if (!brewing) return;

            timer += Time.deltaTime;
            float dur = pending.BrewSeconds * pendingQty;
            // 熬煮動畫：六格循環播完整段
            if (frames.Length > 0)
                ShowFrame(Mathf.FloorToInt(timer / dur * frames.Length * 2f) % frames.Length);

            if (timer >= dur)
            {
                brewing = false;
                ShowFrame(0);
                PotionRecipes.Produce(pending, pendingQty);
                DailyLog.RecordBrew(pendingQty);
                QuestLog.Record(ObjKind.Brew, pending.Name, pendingQty);
                Sfx.Play("brew");
                Popup($"＋{pending.Name} ×{pendingQty}");
                pending = null;
            }
        }

        /// <summary>開始熬煮（BrewPanel 選好配方與份數後呼叫）。材料在這裡就扣掉。</summary>
        public void StartBrew(Recipe r, int qty = 1)
        {
            if (brewing || r == null || qty <= 0) return;
            if (!PotionRecipes.Consume(r, qty)) return;
            brewing = true;
            pending = r;
            pendingQty = qty;
            timer = 0f;
            Popup($"開始熬煮 {r.Name}…");
        }

        public bool IsBrewing => brewing;

        // ──────────── 提示與冒字 ────────────

        void BuildHint()
        {
            hint = MakeText(transform, "按 E 調配藥水", new Vector3(0f, 120f, 0f),
                            new Color32(255, 244, 214, 255));
            hint.SetActive(false);
        }

        void Popup(string msg)
        {
            var go = MakeText(null, msg, transform.position + new Vector3(0f, 140f, 0f),
                              new Color32(214, 236, 255, 255));
            go.AddComponent<FloatAway>().Begin(new Vector3(0f, 42f, 0f), 1.2f, 0.5f);
        }

        static GameObject MakeText(Transform parent, string str, Vector3 pos, Color32 color)
        {
            var go = new GameObject("text");
            if (parent != null) { go.transform.SetParent(parent, false); go.transform.localPosition = pos; }
            else go.transform.position = pos;

            var tm = go.AddComponent<TextMesh>();
            tm.text = str;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = color;

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = 9400;
            return go;
        }
    }
}
