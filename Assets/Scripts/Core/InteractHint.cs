using System;
using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    // ════════════════════════════════════════════════════════════════════════════════
    //  互動提示（2026-11-28）：所有「走近就冒、按 E 做事」的地方共用一套 ——
    //    [E 鍵帽][動作圖]（門是 [門][目的地]、沒有鍵帽），不寫句子（使用者：「提示用圖不用字」、
    //    「每個可以互動的地方都要有像貓那樣的提示，很清楚很可愛」）。
    //
    //  四個部分：
    //    HintLook       提示長什麼樣（鍵帽、動作圖、第二張小圖、變暗、舊版文字）
    //    InteractHint   世界空間的提示本體：彈出來、輕輕上下晃、離開範圍淡出；永遠正立、不跟物件翻面
    //    Interactable   掛在可以互動的物件上：範圍、距離從哪裡量、能不能用、按 E 做什麼、提示長怎樣、提示放哪
    //    Interact       每幀挑出「這一幀 E 給誰」—— 全場景只有一個提示、按 E 只觸發那一個（最近的贏）
    //  另外：IconPopup（做完事冒出來的圖示＋數量）、StatusBubble（花圃缺水的小水滴那種狀態泡泡）。
    //
    //  開關 InteractHint.Enabled＝false：提示退回舊的一行字（各處傳進來的 Legacy 文字），挑選規則不變。
    // ════════════════════════════════════════════════════════════════════════════════

    /// <summary>提示長什麼樣。Key＝鍵帽圖名（icons8 的 key_e…；null＝沒有鍵帽，例如走上去就會進去的門）。</summary>
    public struct HintLook
    {
        public string Key;
        public Sprite Icon;          // 動作圖（必填）
        public Sprite Extra;         // 第二張小圖（門的目的地）
        public bool Dim;             // 變暗：現在按了也做不成（沒種子、鍋子在煮）
        public string Legacy;        // 開關關掉時顯示的舊文字
        public Color32 LegacyColor;

        public static readonly Color32 DefaultLegacyColor = new(255, 244, 214, 255);

        /// <summary>[E][icon]。</summary>
        public static HintLook E(Sprite icon, string legacy, bool dim = false, Sprite extra = null) => new()
        {
            Key = "key_e", Icon = icon, Extra = extra, Dim = dim, Legacy = legacy, LegacyColor = DefaultLegacyColor,
        };

        /// <summary>沒有鍵帽：[icon][extra]（門、地圖邊界的出口）。</summary>
        public static HintLook Plain(Sprite icon, Sprite extra, string legacy) => new()
        {
            Key = null, Icon = icon, Extra = extra, Legacy = legacy, LegacyColor = DefaultLegacyColor,
        };

        public HintLook WithLegacyColor(Color32 c) { LegacyColor = c; return this; }
    }

    /// <summary>提示用的圖：icons8（UiIcons）、items8 的檔名、道具名（GameArt.Item）、目的地場景 → 小圖。</summary>
    public static class HintIcons
    {
        static readonly Dictionary<string, Sprite> items8 = new();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => items8.Clear();

        public static Sprite Ui(string name) => UI.UiIcons.Get(name);

        /// <summary>items8 裡的圖（用檔名，例如 water-drop、potion_pink、lavender）。缺圖回 null。</summary>
        public static Sprite Items8(string file)
        {
            if (items8.TryGetValue(file, out var s) && s != null) return s;
            var t = Resources.Load<Texture2D>("items8/" + file);
            s = t != null ? SheetSlicer.Whole(t) : null;
            items8[file] = s;
            return s;
        }

        /// <summary>道具名 → 圖（背包裡的那張）。</summary>
        public static Sprite Item(string name) => string.IsNullOrEmpty(name) ? null : GameArt.Item(name);

        /// <summary>門／邊界出口通往哪個場景 → 目的地小圖。</summary>
        public static Sprite Destination(string scene) => scene switch
        {
            "shop" => Ui("dest_shop"),
            "town" => Ui("dest_town"),
            "brew" => Ui("dest_cauldron"),
            "main" => Ui("dest_tree"),
            "garden" => Items8("lavender"),
            "candy" => Items8("item-lollipop"),
            _ => null,
        };
    }

    /// <summary>
    /// 世界空間的提示本體（自己一個根物件，不掛在互動物件底下 —— 物件可能縮放、翻面；提示永遠正立）。
    /// 位置＝提示的**底邊中央**（Show 傳進來的點），整組往上長。
    /// </summary>
    public class InteractHint : MonoBehaviour
    {
        /// <summary>開關：false ＝ 退回舊的一行字提示（同一套挑選規則）。</summary>
        public static bool Enabled = true;

        /// <summary>鍵帽與動作圖的顯示高度（icons8 是 96px ＝ 24 格 ×4 → ×0.3，一格 1.2px，跟原本貓頭上的鍵帽一樣）。</summary>
        public const float IconH = 28.8f;
        /// <summary>門的目的地小圖的高度。</summary>
        public const float ExtraH = 22f;
        const float Gap = 1f;
        public const int Order = 9400;

        static readonly Color DimKey = new(0.55f, 0.55f, 0.62f, 1f);
        static readonly Color DimIcon = new(0.62f, 0.62f, 0.7f, 1f);

        SpriteRenderer keySr, iconSr, extraSr, plateSr;
        TextMesh legacy;
        Transform body;
        float alpha, target, popT = -1f, bobSeed;
        Vector3 at;
        string lastKey;
        Sprite lastIcon, lastExtra;
        bool lastDim, lastEnabled = true;
        string lastLegacy;

        public static InteractHint Create(string name)
        {
            var go = new GameObject(name + "-hint");
            return go.AddComponent<InteractHint>();
        }

        void Awake()
        {
            body = new GameObject("body").transform;
            body.SetParent(transform, false);
            plateSr = MakeSr("plate", Order - 1);
            keySr = MakeSr("key", Order);
            iconSr = MakeSr("icon", Order + 1);
            extraSr = MakeSr("extra", Order + 1);
            bobSeed = UnityEngine.Random.value * 6f;
            SetVisible(false);
        }

        SpriteRenderer MakeSr(string n, int order)
        {
            var go = new GameObject(n);
            go.transform.SetParent(body, false);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sortingOrder = order;
            return sr;
        }

        /// <summary>這一幀要顯示（每幀叫）。worldAt＝提示底邊中央。</summary>
        public void Show(Vector3 worldAt, in HintLook look)
        {
            at = worldAt;
            Apply(look);
            if (target < 0.5f)
            {
                target = 1f;
                if (alpha < 0.05f) popT = 0f;       // 從看不見到看得見：彈一下
            }
        }

        /// <summary>收起來（淡出）。</summary>
        public void Hide() => target = 0f;

        void Apply(in HintLook look)
        {
            if (look.Key == lastKey && look.Icon == lastIcon && look.Extra == lastExtra && look.Dim == lastDim
                && lastEnabled == Enabled && look.Legacy == lastLegacy) return;
            lastKey = look.Key; lastIcon = look.Icon; lastExtra = look.Extra; lastDim = look.Dim;
            lastEnabled = Enabled; lastLegacy = look.Legacy;

            if (!Enabled)
            {
                keySr.sprite = iconSr.sprite = extraSr.sprite = plateSr.sprite = null;
                if (legacy == null) legacy = MakeLegacy();
                legacy.text = look.Legacy ?? "";
                legacy.color = look.LegacyColor;
                return;
            }
            if (legacy != null) legacy.text = "";

            var key = string.IsNullOrEmpty(look.Key) ? null : UI.UiIcons.Get(look.Key);
            float kw = Place(keySr, key, IconH);
            float iw = Place(iconSr, look.Icon, IconH);
            float ew = Place(extraSr, look.Extra, ExtraH);
            int parts = (kw > 0 ? 1 : 0) + (iw > 0 ? 1 : 0) + (ew > 0 ? 1 : 0);
            float total = kw + iw + ew + Gap * Mathf.Max(0, parts - 1);
            float x = -total / 2f;
            if (kw > 0) { keySr.transform.localPosition = new Vector3(x + kw / 2f, IconH / 2f, 0f); x += kw + Gap; }
            if (iw > 0) { iconSr.transform.localPosition = new Vector3(x + iw / 2f, IconH / 2f, 0f); x += iw + Gap; }
            if (ew > 0) extraSr.transform.localPosition = new Vector3(x + ew / 2f, ExtraH / 2f + 2f, 0f);
            // 沒有鍵帽的（門、邊界出口）墊一塊小牌子：不然兩張小圖貼在門上，看起來像場景的一部分
            plateSr.sprite = kw > 0 ? null : Plate(Mathf.CeilToInt(total) + 8, Mathf.CeilToInt(IconH) + 6);
            plateSr.transform.localPosition = new Vector3(0f, IconH / 2f, 0f);
            keySr.color = look.Dim ? DimKey : Color.white;
            iconSr.color = look.Dim ? DimIcon : Color.white;
            extraSr.color = Color.white;
        }

        static readonly Dictionary<long, Sprite> plates = new();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetPlates() => plates.Clear();

        /// <summary>
        /// 門那種提示的底牌：深紫半透明、1px 淡米色邊、四角各切一格（像素風的圓角）。程式生成、照尺寸快取。
        /// </summary>
        static Sprite Plate(int w, int h)
        {
            long k = ((long)w << 16) | (uint)h;
            if (plates.TryGetValue(k, out var sp) && sp != null) return sp;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            var px = new Color32[w * h];
            var fill = new Color32(40, 26, 54, 175);
            var edge = new Color32(246, 232, 198, 210);
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    bool corner = (x == 0 || x == w - 1) && (y == 0 || y == h - 1);
                    bool border = x == 0 || y == 0 || x == w - 1 || y == h - 1
                                  || ((x == 1 || x == w - 2) && (y == 1 || y == h - 2));
                    bool cut = corner || ((x == 0 || x == w - 1) && (y == 1 || y == h - 2)) || ((y == 0 || y == h - 1) && (x == 1 || x == w - 2));
                    px[y * w + x] = cut ? new Color32(0, 0, 0, 0) : border ? edge : fill;
                }
            tex.SetPixels32(px);
            tex.Apply();
            sp = Sprite.Create(tex, new Rect(0, 0, w, h), new Vector2(0.5f, 0.5f), 1f, 0, SpriteMeshType.FullRect);
            plates[k] = sp;
            return sp;
        }

        /// <summary>把圖縮到指定高度；回傳顯示寬度（沒圖＝0）。圖的樞紐要在中心（SheetSlicer.Whole 的預設）。</summary>
        static float Place(SpriteRenderer sr, Sprite sp, float h)
        {
            sr.sprite = sp;
            if (sp == null) return 0f;
            float k = h / sp.rect.height;
            sr.transform.localScale = new Vector3(k, k, 1f);
            return sp.rect.width * k;
        }

        TextMesh MakeLegacy()
        {
            var go = new GameObject("legacy");
            go.transform.SetParent(body, false);
            go.transform.localPosition = new Vector3(0f, 12f, 0f);
            var tm = go.AddComponent<TextMesh>();
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = Order;
            return tm;
        }

        bool visible = true;

        void SetVisible(bool on)
        {
            if (visible == on) return;
            visible = on;
            body.gameObject.SetActive(on);
        }

        void LateUpdate()
        {
            float dt = Time.deltaTime;
            alpha = Mathf.MoveTowards(alpha, target, dt * (target > alpha ? 9f : 6f));
            if (alpha <= 0f && target <= 0f) { SetVisible(false); return; }
            SetVisible(true);

            // 彈出：0.6 → 1.12 → 1（0.22 秒）
            float s = 1f;
            if (popT >= 0f)
            {
                popT += dt;
                float k = Mathf.Clamp01(popT / 0.22f);
                s = k < 0.6f ? Mathf.Lerp(0.6f, 1.12f, k / 0.6f) : Mathf.Lerp(1.12f, 1f, (k - 0.6f) / 0.4f);
                if (k >= 1f) popT = -1f;
            }
            body.localScale = new Vector3(s, s, 1f);
            float bob = Mathf.Sin(Time.time * 3f + bobSeed) * 1.5f;
            transform.position = new Vector3(Mathf.Round(at.x), Mathf.Round(at.y + bob), 0f);

            SetAlpha(keySr, alpha);
            SetAlpha(iconSr, alpha);
            SetAlpha(extraSr, alpha);
            SetAlpha(plateSr, alpha);
            if (legacy != null) { var c = legacy.color; c.a = alpha; legacy.color = c; }
        }

        static void SetAlpha(SpriteRenderer sr, float a)
        {
            if (sr.sprite == null) return;
            var c = sr.color;
            c.a = a;
            sr.color = c;
        }
    }

    /// <summary>
    /// 可以互動的東西（掛在物件上；OnEnable 登記、OnDisable 撤掉）。欄位都是生成後直接指派：
    ///   range     按 E 的範圍（女巫腳底到 <see cref="Point"/> 的距離；0 ＝不吃 E，只顯示，例如地圖邊界的出口）
    ///   showRange 沒有鍵帽的提示（門）在多遠就顯示（≥ range；0 ＝跟 range 一樣）
    ///   keyed     提示有沒有鍵帽。**有鍵帽的優先**：範圍內只要有一個，門的提示就不出來、E 也不會進門
    ///   point / available / use / look / anchor  見各自說明
    /// </summary>
    public class Interactable : MonoBehaviour
    {
        public float range = 100f;
        public float showRange;
        public bool keyed = true;
        /// <summary>量距離的那一點（null ＝ transform.position）。</summary>
        public Func<Vector2> point;
        /// <summary>現在能不能互動（false ＝ 不算進挑選、不顯示；例如採光了的樹、還沒解鎖的門）。null ＝ 可以。</summary>
        public Func<bool> available;
        /// <summary>按 E 做的事（null ＝ 不吃 E）。</summary>
        public Action use;
        /// <summary>提示長什麼樣（只有顯示的那一個每幀問一次）。</summary>
        public Func<HintLook> look;
        /// <summary>提示底邊放哪（世界座標）。null ＝ 自動：物件上所有圖的最上緣 +6，但最多比 <see cref="Point"/> 高 <see cref="maxRise"/>
        /// （高大的樹、房子不會飄到天上）；物件沒有圖（隱形觸發點）就是 Point 往上 <see cref="fallbackRise"/>。</summary>
        public Func<Vector3> anchor;
        public float maxRise = 150f;
        public float fallbackRise = 70f;
        /// <summary>暫時不顯示提示（還是照樣吃 E；例如貓被摸的那一下）。</summary>
        public Func<bool> hideHint;

        InteractHint hint;

        public Vector2 Point => point != null ? point() : (Vector2)transform.position;
        public bool Available => available == null || available();

        /// <summary>方便的建構：掛上去並設好常用的欄位。</summary>
        public static Interactable Attach(GameObject go, float range, Action use, Func<HintLook> look)
        {
            var it = go.AddComponent<Interactable>();
            it.range = range;
            it.use = use;
            it.look = look;
            return it;
        }

        void OnEnable() => Interact.Register(this);

        void OnDisable()
        {
            Interact.Unregister(this);
            if (hint != null) hint.Hide();
        }

        void OnDestroy()
        {
            if (hint != null) Destroy(hint.gameObject);
        }

        internal void SetShown(bool on)
        {
            if (!on || (hideHint != null && hideHint()))
            {
                if (hint != null) hint.Hide();
                return;
            }
            if (look == null) return;
            if (hint == null) hint = InteractHint.Create(name);
            hint.Show(HintAnchor(), look());
        }

        public Vector3 HintAnchor()
        {
            if (anchor != null) return anchor();
            var p = Point;
            float top = float.MinValue;
            foreach (var sr in GetComponentsInChildren<SpriteRenderer>())
                if (sr.enabled && sr.sprite != null) top = Mathf.Max(top, sr.bounds.max.y);
            float y = top > float.MinValue ? Mathf.Min(top + 6f, p.y + maxRise) : p.y + fallbackRise;
            return new Vector3(p.x, y, 0f);
        }
    }

    /// <summary>
    /// 每幀挑一次「E 給誰、提示給誰」（場景裡第一個 Interactable 登記時自己生出來，換場景跟著消失）。
    ///
    /// 規則（不改任何互動的範圍、也不改按了做什麼）：
    ///   ① <see cref="Suspended"/>（開著面板、對話、睡覺過場、換場景淡出、店裡／後花園／家裡的佈置模式）→ 什麼都不顯示、E 不作用；
    ///      剛恢復的那一兩幀也不吃 E（對話框、每日結算是按 E 關的，同一下 E 不能又觸發世界裡的東西）。
    ///   ② 有鍵帽的（keyed）：女巫在 range 內、available 的那些裡**最近的**一個 → 這一幀的 E 與提示都給它。
    ///   ③ 範圍內一個有鍵帽的都沒有 → 沒鍵帽的（門、邊界出口）在 showRange 內最近的那個顯示；
    ///      它若也在自己的 range 內而且有 use（門），E 給它（照舊可以按 E 進門）。
    ///   → 任何時候畫面上最多一個提示，而且就是 E 會觸發的那一個。
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class Interact : MonoBehaviour
    {
        static readonly List<Interactable> all = new();
        static readonly HashSet<object> holds = new();
        static Interact driver;
        static Transform player;
        static int lastSuspendedFrame = -99;

        /// <summary>這一幀 E 會觸發的那一個（沒有＝null）。</summary>
        public static Interactable Focus { get; private set; }
        /// <summary>這一幀畫面上顯示提示的那一個（通常＝Focus；只有門那種沒鍵帽的會是 Shown 但不一定是 Focus）。</summary>
        public static Interactable Shown { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            all.Clear(); holds.Clear(); driver = null; player = null; Focus = null; Shown = null; lastSuspendedFrame = -99;
        }

        /// <summary>
        /// 互動暫停中（世界裡的提示全收、E 不作用）。看得到的狀態直接問（不會因為誰忘了解除而卡住）；
        /// 新的模式要暫停互動：<see cref="Hold"/> / <see cref="Release"/>。
        /// </summary>
        public static bool Suspended =>
            UIState.ModalOpen
            || UI.SceneFade.Busy
            || HomeArrange.Busy
            || (ShopRoomEditor.Instance != null && ShopRoomEditor.Instance.Editing)
            || (GardenArrange.Instance != null && GardenArrange.Instance.Editing)
            || holds.Count > 0;

        /// <summary>某個模式開始：暫停互動（who 隨便給一個識別物件，Release 時給同一個）。</summary>
        public static void Hold(object who) { if (who != null) holds.Add(who); }
        public static void Release(object who) { if (who != null) holds.Remove(who); }

        /// <summary>剛從暫停恢復（這一幀或上一幀還在暫停）—— 自己處理 E 的地方也該看這個。</summary>
        public static bool JustResumed => Time.frameCount - lastSuspendedFrame <= 1;

        internal static void Register(Interactable it)
        {
            if (!all.Contains(it)) all.Add(it);
            if (driver == null) driver = new GameObject("Interact").AddComponent<Interact>();
        }

        internal static void Unregister(Interactable it)
        {
            all.Remove(it);
            if (Focus == it) Focus = null;
            if (Shown == it) Shown = null;
        }

        void OnDestroy()
        {
            if (driver == this) { driver = null; player = null; }
        }

        void Update()
        {
            if (player == null)
            {
                var p = GameObject.Find("Player");
                player = p != null ? p.transform : null;
            }

            Interactable focus = null, shown = null;
            bool sus = Suspended;
            if (sus) lastSuspendedFrame = Time.frameCount;
            else if (player != null) Pick(player.position, out focus, out shown);
            Focus = focus;
            Shown = shown;

            for (int i = all.Count - 1; i >= 0; i--)
            {
                var it = all[i];
                if (it == null) { all.RemoveAt(i); continue; }
                it.SetShown(it == shown);
            }

            if (focus != null && !JustResumed && Input.GetKeyDown(KeyCode.E)) focus.use?.Invoke();
        }

        static void Pick(Vector2 pp, out Interactable focus, out Interactable shown)
        {
            Interactable keyed = null, plain = null;
            float bk = float.MaxValue, bp = float.MaxValue, plainD = 0f;
            foreach (var it in all)
            {
                if (it == null || !it.isActiveAndEnabled || !it.Available) continue;
                float d = Vector2.Distance(pp, it.Point);
                if (it.keyed)
                {
                    if (it.use != null && it.range > 0f && d <= it.range && d < bk) { bk = d; keyed = it; }
                }
                else
                {
                    float sr = Mathf.Max(it.range, it.showRange);
                    if (d <= sr && d < bp) { bp = d; plain = it; plainD = d; }
                }
            }
            if (keyed != null) { focus = keyed; shown = keyed; return; }
            shown = plain;
            focus = plain != null && plain.use != null && plain.range > 0f && plainD <= plain.range ? plain : null;
        }
    }

    /// <summary>做完事冒出來的小圖：[圖][第二張小圖][×N]，往上飄、淡出（開關關掉時退回舊的一行字）。</summary>
    public static class IconPopup
    {
        public static void Show(Vector3 at, Sprite icon, string count = null, Sprite icon2 = null, string legacy = null)
        {
            if (!InteractHint.Enabled || icon == null)
            {
                if (!string.IsNullOrEmpty(legacy)) TextPopup(at, legacy);
                return;
            }
            var go = new GameObject("icon-popup");
            go.transform.position = new Vector3(at.x, at.y, 0f);
            const float H = 26f;
            float w1 = Put(go.transform, icon, H, 9500);
            float w2 = icon2 != null ? Put(go.transform, icon2, 18f, 9501) : 0f;
            float tw = string.IsNullOrEmpty(count) ? 0f : count.Length * 11f;
            float total = w1 + w2 + tw + (w2 > 0 ? 1f : 0f) + (tw > 0 ? 2f : 0f);
            float x = -total / 2f;
            var kids = go.GetComponentsInChildren<SpriteRenderer>();
            kids[0].transform.localPosition = new Vector3(x + w1 / 2f, 0f, 0f);
            x += w1 + 1f;
            if (w2 > 0) { kids[1].transform.localPosition = new Vector3(x + w2 / 2f, -4f, 0f); x += w2 + 1f; }
            if (tw > 0) Count(go.transform, count, new Vector3(x + tw / 2f, 0f, 0f));
            go.AddComponent<FloatAway>().Begin(new Vector3(0f, 40f, 0f), 1.1f, 0.5f);
        }

        static float Put(Transform parent, Sprite sp, float h, int order)
        {
            var go = new GameObject("img");
            go.transform.SetParent(parent, false);
            float k = h / sp.rect.height;
            go.transform.localScale = new Vector3(k, k, 1f);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
            return sp.rect.width * k;
        }

        /// <summary>數量（×N）：深色錯開一份當描邊，同採集的飄字。</summary>
        static void Count(Transform parent, string str, Vector3 pos)
        {
            var font = UI.CjkFont.Get();
            for (int pass = 0; pass < 2; pass++)
            {
                bool shadow = pass == 0;
                var go = new GameObject(shadow ? "count-shadow" : "count");
                go.transform.SetParent(parent, false);
                go.transform.localPosition = pos + (shadow ? new Vector3(1.5f, -1.5f, 0.01f) : Vector3.zero);
                var tm = go.AddComponent<TextMesh>();
                tm.text = str;
                tm.fontSize = 40;
                tm.characterSize = 5f;
                tm.anchor = TextAnchor.MiddleCenter;
                tm.color = shadow ? new Color32(60, 40, 30, 220) : new Color32(255, 246, 214, 255);
                if (font != null)
                {
                    tm.font = font;
                    go.GetComponent<MeshRenderer>().material = font.material;
                }
                go.GetComponent<MeshRenderer>().sortingOrder = shadow ? 9501 : 9502;
            }
        }

        /// <summary>舊版的一行字（開關關掉時）。</summary>
        public static void TextPopup(Vector3 at, string msg)
        {
            var go = new GameObject("popup");
            go.transform.position = at;
            var tm = go.AddComponent<TextMesh>();
            tm.text = msg;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color32(255, 246, 214, 255);
            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = 9500;
            go.AddComponent<FloatAway>().Begin(new Vector3(0f, 40f, 0f), 1.1f, 0.5f);
        }
    }

    /// <summary>
    /// 狀態小泡泡（花圃缺水的水滴）：一張小圖輕輕上下晃，掛在物件底下（物件不翻面才行 —— 花圃不翻）。
    /// </summary>
    public class StatusBubble : MonoBehaviour
    {
        float baseY, seed;

        public static StatusBubble Create(Transform parent, Vector3 localPos, Sprite sp, float height, int order)
        {
            var go = new GameObject("status");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = order;
            if (sp != null)
            {
                float k = height / sp.rect.height;
                go.transform.localScale = new Vector3(k, k, 1f);
            }
            var b = go.AddComponent<StatusBubble>();
            b.baseY = localPos.y;
            b.seed = UnityEngine.Random.value * 6f;
            return b;
        }

        void LateUpdate()
        {
            var p = transform.localPosition;
            p.y = baseY + Mathf.Round(Mathf.Sin(Time.time * 2.6f + seed) * 2f);
            transform.localPosition = p;
        }
    }
}
