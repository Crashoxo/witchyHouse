using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 泡泡的樣式 —— 依「講的是哪一類話」決定（呼叫端指定，**不從文字猜**）。
    /// 對應見 CustomerManager 的「說話」一段與 PORTING.md 2026-11-28 對話泡泡樣式。
    /// </summary>
    public enum BubbleKind
    {
        /// <summary>一般說話：奶油色圓角＋圓尾巴（招呼、結伴對話、逛完要走的話）。</summary>
        Normal,
        /// <summary>開心／要買：粉紅飾邊＋角落小愛心（想要 X、道謝）。</summary>
        Happy,
        /// <summary>在想事情：雲朵框＋三顆小圓點代替尾巴（只逛不買的人在商品前的評論）。</summary>
        Think,
        /// <summary>失望：冷灰紫＋角落汗珠（想要的賣完了）。</summary>
        Sad,
        /// <summary>喊出來：金色爆炸框＋長尖刺尾巴＋小閃光（成交的 +金額）。</summary>
        Shout,
    }

    /// <summary>純圖示泡泡（<see cref="SpeechBubble.ShowIcon"/>）或文字前面可以放的小符號。</summary>
    public enum BubbleGlyph { Heart, Note, Dots, Coin }

    /// <summary>
    /// 世界空間的對話泡：泡泡框 ＋（可選）道具圖示 ＋ 文字。
    /// 顧客進門招呼、想買什麼、成交了沒、只逛不買的評論都用它。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用 Graphics 即時畫圓角矩形（roundRect + fill + stroke），還要手畫小尾巴。
    /// Unity 沒有等價的即時繪圖元件，所以底圖是九宮格 Sprite，用 sliced／tiled 模式撐開，任何尺寸都不會變形。
    ///
    /// ⚠️ 文字用 TextMesh 不是 TextMeshPro —— 同 GatherTree 的理由：TextMesh 吃得下
    ///    動態字型，中文不用先烘 FontAsset。
    ///
    /// ── 11/26 改版 ─────────────────────────────────────────────
    ///   ① 寬度依文字長度決定（量字型的 advance），太長就拆行。
    ///   ② 存在時間：life &gt; 0 的泡泡幾秒後自己淡出消失（life = 0 ＝ 一直掛著）。
    ///   ③ 重疊錯開：多位顧客站在一起時，新的泡泡往上抬到不壓住舊的（見 <see cref="BubbleLife"/>）。
    ///   ④ 翻面修正：每幀依父物件的 lossyScale 反轉回來，角色說話中轉身文字也不會鏡像。
    ///
    /// ── 11/28 細畫版（<see cref="UsePixelBubbles"/>）──────────────────
    /// 泡泡框改用 tools/gen_bubble_art.py 畫的 1 px 像素圖（Resources/bubbles8/，遊戲裡 ×1.6，跟女巫同一套），
    /// 五種樣式（<see cref="BubbleKind"/>）＋純圖示泡泡（<see cref="ShowIcon"/>）。
    ///   ● 九宮格邊界寫在程式裡（<see cref="Frames"/>），Sprite 在這裡用 Sprite.Create 帶邊界建 —— 不用手寫 .meta。
    ///     ⚠️ 數字要跟產生器的 SPECS／TAIL_AT 對得上（產生器跑完會印一張對照表）。
    ///   ● 雲朵／爆炸框的邊是週期花樣，用 SpriteDrawMode.Tiled 重複中央那一格；尺寸一律對齊到整數格（<see cref="Snap"/>），
    ///     花樣才接得上。普通三種用 Sliced。
    ///   ● 尾巴是另一張圖，蓋在泡泡底邊上（蓋掉那一段外輪廓）；泡泡被畫面邊緣推開時換成斜的尾巴、翻面指回說話的人。
    ///   ● 彈出（0.6 → 回彈 → 1）、輕輕上下浮、結束時縮小淡出；想事情的小圓點一顆一顆冒出來。
    ///   ● 關掉開關（或 bubbles8 的圖不見）就回到舊的程式生成圓角泡泡，外觀跟 11/26 版一樣。
    /// </summary>
    public static class SpeechBubble
    {
        /// <summary>細畫版泡泡開關（false ＝ 舊的程式生成深色圓角泡泡）。</summary>
        public static bool UsePixelBubbles = true;

        // ──────────── 共用的排版常數（世界 px）────────────

        /// <summary>第二行起每行多出來的高度。⚠️ 要跟 TextMesh 的 lineSpacing 對得上（見 MakeText）。</summary>
        const float LineH = 20f;
        /// <summary>一行文字最寬多少 px，超過就拆行（≈ 11 個中文字）；最多三行。</summary>
        const float MaxLineW = 176f;

        // 字級：TextMesh 的世界大小 ≈ fontSize × characterSize ÷ 10（見 GatherTree 的換算說明）
        const int FontSize = 36;
        const float CharSize = 4.5f;          // ≈ 16px 高
        const float Em = FontSize * CharSize / 10f;

        // ──────────── 舊版（UsePixelBubbles = false）────────────

        const float H1 = 46f;
        const float MinW = 64f;
        const float PadX = 14f;
        const float IconSpace = 40f;
        const int Radius = 12;

        // ──────────── 細畫版 ────────────

        /// <summary>1 原生像素 = 幾個世界 px（同 GameArt.WitchScale）。</summary>
        const float Px = 1.6f;
        /// <summary>細畫版泡泡最窄多寬（世界 px）——「好」一個字也不要縮成一顆小豆子。</summary>
        const float PixMinW = 44f;
        /// <summary>帶道具圖示時圖示佔的寬（道具圖四周有透明邊，內容 ≈ 28px）。</summary>
        const float PixIconSpace = 26f;
        /// <summary>泡泡裡的道具圖示：最長邊（經 ItemIconWorld 換算）。</summary>
        const float PixIconPx = 28f;
        /// <summary>尾巴尖端離頭頂多高。</summary>
        const float TipGap = 2f;
        /// <summary>想事情泡泡：本體底邊離頭頂多高（中間放三顆小圓點）。</summary>
        const float ThinkDotsH = 27f;

        /// <summary>
        /// 一種泡泡框的規格（原生 px）。L/R/T/B ＝ 九宮格四邊（B 含 2 列落影）；P/PV ＝ 中央一格（Tiled 類＝花樣週期）；
        /// PadX/PadT/PadB ＝ 文字區離樣板邊緣多遠；TailAt ＝ 尾巴圖最上面一列在樣板底邊上幾列；
        /// TailInset ＝ 尾巴中心離泡泡左右邊至少多遠（避開圓角／角落尖刺）。
        /// ⚠️ 跟 tools/gen_bubble_art.py 的 SPECS、TAIL_AT 一起改。
        /// </summary>
        struct FrameSpec
        {
            public string Name;
            public int L, R, T, B, P, PV;
            public int PadX, PadT, PadB;
            public bool Tiled;
            public int TailAt;
            public float TailInset;
            public Color32 Ink;
        }

        const int ShadowRows = 2;

        static readonly FrameSpec[] Frames =
        {
            // Normal
            new FrameSpec { Name = "normal", L = 6, R = 6, T = 6, B = 8, P = 2, PV = 2, PadX = 7, PadT = 5, PadB = 7,
                            Tiled = false, TailAt = 5, TailInset = 9f, Ink = new Color32(0x4a, 0x2a, 0x35, 255) },
            // Happy
            new FrameSpec { Name = "happy", L = 6, R = 6, T = 6, B = 8, P = 2, PV = 2, PadX = 7, PadT = 5, PadB = 7,
                            Tiled = false, TailAt = 5, TailInset = 9f, Ink = new Color32(0x4a, 0x2a, 0x35, 255) },
            // Think
            new FrameSpec { Name = "think", L = 11, R = 11, T = 11, B = 13, P = 11, PV = 2, PadX = 8, PadT = 7, PadB = 9,
                            Tiled = true, TailAt = 0, TailInset = 9f, Ink = new Color32(0x40, 0x30, 0x4e, 255) },
            // Sad
            new FrameSpec { Name = "sad", L = 6, R = 6, T = 6, B = 8, P = 2, PV = 2, PadX = 7, PadT = 5, PadB = 7,
                            Tiled = false, TailAt = 5, TailInset = 9f, Ink = new Color32(0x3a, 0x30, 0x48, 255) },
            // Shout
            new FrameSpec { Name = "shout", L = 12, R = 12, T = 11, B = 13, P = 12, PV = 2, PadX = 9, PadT = 8, PadB = 10,
                            Tiled = true, TailAt = 11, TailInset = 13.5f, Ink = new Color32(0x5a, 0x2a, 0x14, 255) },
        };

        static string OrnamentOf(BubbleKind k) => k switch
        {
            BubbleKind.Happy => "orn-heart",
            BubbleKind.Shout => "orn-sparkle",
            BubbleKind.Sad => "orn-sweat",
            _ => null,
        };

        static string GlyphName(BubbleGlyph g) => g switch
        {
            BubbleGlyph.Heart => "glyph-heart",
            BubbleGlyph.Note => "glyph-note",
            BubbleGlyph.Dots => "glyph-dots",
            _ => "glyph-coin",
        };

        // ──────────── 對外 API ────────────

        /// <summary>
        /// 在 parent 頭頂 headHeight 的地方掛一個對話泡（會先移除舊的）。
        /// </summary>
        /// <param name="parent">要掛在誰身上</param>
        /// <param name="headHeight">這個角色的顯示高度（泡泡擺在它上方）</param>
        /// <param name="icon">左邊的小圖示（null＝只有文字）。道具圖或 <see cref="Glyph"/> 的符號都可以</param>
        /// <param name="text">內容（太長會自動拆行；也可以自己放 \n）</param>
        /// <param name="bg">底色（只有舊版泡泡用；細畫版的顏色由 kind 決定）</param>
        /// <param name="life">幾秒後自動淡出消失；0 ＝ 一直掛著（直到被下一個蓋掉或 Clear）</param>
        /// <param name="kind">細畫版的樣式（舊的呼叫端不給 ＝ 一般說話）</param>
        public static GameObject Show(Transform parent, float headHeight,
                                      Sprite icon, string text, Color32 bg, float life = 0f,
                                      BubbleKind kind = BubbleKind.Normal)
        {
            Clear(parent);
            text ??= "";
            if (UsePixelBubbles && ArtReady())
                return BuildPixel(parent, headHeight, icon, text, kind, life, false);
            // 舊版不認識新的符號圖（+金額的金幣之類）—— 當作沒有圖示，跟以前一模一樣
            if (IsGlyph(icon)) icon = null;
            return BuildLegacy(parent, headHeight, icon, text, bg, life);
        }

        /// <summary>
        /// 純圖示的小泡泡（沒有字）：一顆愛心、音符、「…」，或一樣道具。給很短的反應用（使用者偏好圖不用字）。
        /// 舊版泡泡（開關關掉、或圖不見）不顯示，回 null。
        /// </summary>
        public static GameObject ShowIcon(Transform parent, float headHeight, Sprite icon,
                                          BubbleKind kind = BubbleKind.Normal, float life = 1.6f)
        {
            if (parent == null || icon == null || !UsePixelBubbles || !ArtReady()) return null;
            Clear(parent);
            return BuildPixel(parent, headHeight, icon, "", kind, life, true);
        }

        /// <summary>泡泡用的小符號（顯示 ×1.6 的原生像素圖）；圖不見回 null。</summary>
        public static Sprite Glyph(BubbleGlyph g) => ArtReady() ? Spr(GlyphName(g), new Vector2(0.5f, 0.5f)) : null;

        /// <summary>移除某個角色身上的對話泡。</summary>
        public static void Clear(Transform parent)
        {
            if (parent == null) return;
            // ⚠️ 不能只用 parent.Find("bubble") 然後 Destroy —— Destroy 要到這一幀結束才生效，
            //    同一幀連叫兩次 Show 時，第二次的 Find 會又找到那個「已排定銷毀」的舊泡泡，
            //    反而把剛生的新泡泡留下來 → 頭上疊兩顆。所以先改名、關掉，再排銷毀。
            for (int i = parent.childCount - 1; i >= 0; i--)
            {
                var ch = parent.GetChild(i);
                if (ch.name != "bubble") continue;
                ch.name = "bubble-dead";
                ch.gameObject.SetActive(false);
                Object.Destroy(ch.gameObject);
            }
        }

        // ──────────── 細畫版 ────────────

        static GameObject BuildPixel(Transform parent, float headHeight, Sprite icon, string text,
                                     BubbleKind kind, float life, bool iconOnly)
        {
            var spec = Frames[(int)kind];
            var font = UI.CjkFont.Get();
            bool glyphIcon = IsGlyph(icon);

            // ── 內容的大小（世界 px）──
            string body = "";
            float textW = 0f, iconW = 0f, iconH = 0f, iconScale = 1f;
            int lines = 1;
            if (icon != null)
            {
                if (glyphIcon) { iconW = icon.rect.width * Px; iconH = icon.rect.height * Px; }
                else
                {
                    // 道具圖：最長邊 PixIconPx（8-bit 道具圖四周有透明邊，經 ItemIconWorld 放大，看起來才一樣大）
                    iconScale = GameArt.ItemIconWorld(PixIconPx) / Mathf.Max(icon.rect.width, icon.rect.height);
                    iconW = icon.rect.width * iconScale; iconH = icon.rect.height * iconScale;
                }
            }
            int wN, hN;
            float iconSpace = 0f;
            if (iconOnly)
            {
                // 純圖示：內距各少 2 px，圓胖一點（同產生器的 render_bubble icon_only）
                float cw = glyphIcon ? iconW : iconW * 0.85f;      // 道具圖的透明邊不算
                float ch = glyphIcon ? iconH : iconH * 0.85f;
                wN = Mathf.CeilToInt(cw / Px) + 2 * (spec.PadX - 2);
                hN = Mathf.CeilToInt(ch / Px) + spec.PadT + spec.PadB - 2;
            }
            else
            {
                body = Layout(text, font, out textW, out lines);
                if (icon != null) iconSpace = glyphIcon ? iconW + 4f : PixIconSpace;
                float cw = textW + iconSpace;
                float ch = Em + (lines - 1) * LineH;
                wN = Mathf.CeilToInt(Mathf.Max(PixMinW, cw + 2f * spec.PadX * Px) / Px);
                hN = Mathf.CeilToInt(ch / Px) + spec.PadT + spec.PadB;
            }
            Snap(spec, ref wN, ref hN);
            float w = wN * Px, h = hN * Px;

            int seq = BubbleLife.NextSeq();
            // 排序：新的泡泡畫在舊的上面。⚠️ 上限要停在 9600 以下 —— 成交的表情動畫是 9600，要蓋在泡泡上面。
            int order = 9500 + (seq % 24) * 4;

            var root = new GameObject("bubble");
            root.transform.SetParent(parent, false);

            // 尾巴：本體底邊要墊多高（根物件原點＝尾巴尖端／最下面那顆小圓點，在頭頂上 TipGap）
            Sprite tailC = null, tailS = null;
            float bodyY0;
            if (kind == BubbleKind.Think) bodyY0 = ThinkDotsH;
            else
            {
                tailC = Spr($"tail-{spec.Name}-c", new Vector2(0.5f, 1f));
                tailS = Spr($"tail-{spec.Name}-s", new Vector2(0.5f, 1f));
                bodyY0 = tailC != null ? (tailC.rect.height - spec.TailAt) * Px : 0f;
            }

            // ── 本體（原點＝樣板底邊中央；彈出時從這裡長大）──
            var bodyGo = new GameObject("body");
            bodyGo.transform.SetParent(root.transform, false);
            bodyGo.transform.localPosition = new Vector3(0f, bodyY0, 0f);

            var frame = new GameObject("frame");
            frame.transform.SetParent(bodyGo.transform, false);
            var fsr = frame.AddComponent<SpriteRenderer>();
            fsr.sprite = FrameSprite(spec);
            fsr.drawMode = spec.Tiled ? SpriteDrawMode.Tiled : SpriteDrawMode.Sliced;
            if (spec.Tiled) fsr.tileMode = SpriteTileMode.Continuous;
            fsr.size = new Vector2(w, h);
            fsr.sortingOrder = order;

            // 文字區（扣掉內距）的中心
            float areaY = (spec.PadB + (hN - spec.PadT - spec.PadB) * 0.5f) * Px;

            if (iconOnly)
            {
                AddIcon(bodyGo.transform, icon, new Vector3(0f, areaY, 0f), glyphIcon ? 1f : iconScale, order + 2);
            }
            else
            {
                float cw = textW + iconSpace;
                if (icon != null)
                    AddIcon(bodyGo.transform, icon, new Vector3(-cw / 2f + iconSpace / 2f, areaY, 0f),
                            glyphIcon ? 1f : iconScale, order + 2);
                float textX = -cw / 2f + iconSpace + textW / 2f;
                var tm = MakeText(bodyGo.transform, body, font, new Vector3(textX, areaY, 0f), order + 3);
                tm.color = spec.Ink;
            }

            // 角落小裝飾（純圖示泡泡不放，免得搶戲）
            string orn = iconOnly ? null : OrnamentOf(kind);
            if (orn != null)
            {
                var os = Spr(orn, new Vector2(0.5f, 0.5f));
                if (os != null)
                {
                    float ow = os.rect.width * Px, oh = os.rect.height * Px;
                    float ox = kind == BubbleKind.Sad ? w / 2f - Px - ow / 2f : w / 2f + 3f * Px - ow / 2f;
                    float oy = h + 2f * Px - oh / 2f;
                    var o = new GameObject("ornament");
                    o.transform.SetParent(bodyGo.transform, false);
                    o.transform.localPosition = new Vector3(ox, oy, 0f);
                    var osr = o.AddComponent<SpriteRenderer>();
                    osr.sprite = os;
                    osr.sortingOrder = order + 2;
                }
            }

            // ── 尾巴（掛在根物件下，x 每幀由 BubbleLife 對準說話的人）──
            SpriteRenderer tail = null;
            SpriteRenderer[] dots = null;
            if (kind == BubbleKind.Think)
            {
                dots = new SpriteRenderer[3];
                string[] names = { "dot-s", "dot-m", "dot-l" };      // 由頭頂往上：小 → 大
                for (int i = 0; i < 3; i++)
                {
                    var d = new GameObject(names[i]);
                    d.transform.SetParent(root.transform, false);
                    var dsr = d.AddComponent<SpriteRenderer>();
                    dsr.sprite = Spr(names[i], new Vector2(0.5f, 0.5f));
                    dsr.sortingOrder = order + 1;
                    dsr.enabled = false;
                    dots[i] = dsr;
                }
            }
            else if (tailC != null)
            {
                var t = new GameObject("tail");
                t.transform.SetParent(root.transform, false);
                t.transform.localPosition = new Vector3(0f, bodyY0 + spec.TailAt * Px, 0f);
                tail = t.AddComponent<SpriteRenderer>();
                tail.sprite = tailC;
                tail.sortingOrder = order + 1;
            }

            var geo = new BubbleLife.Geometry
            {
                Body = bodyGo.transform,
                W = w,
                BodyBottom = bodyY0 + ShadowRows * Px,
                BodyTop = bodyY0 + h,
                BodyY0 = bodyY0,
                TailBelow = bodyY0 + ShadowRows * Px,
                Tail = tail,
                TailC = tailC,
                TailS = tailS,
                TailTipC = TipOffset(tailC, false),
                TailTipS = TipOffset(tailS, true),
                TailInset = spec.TailInset * Px,
                Dots = dots,
                Pixel = true,
            };
            float baseY = headHeight + TipGap;
            root.transform.localPosition = new Vector3(0f, baseY, 0f);
            root.AddComponent<BubbleLife>().Init(parent, life, baseY, seq, geo);

            // 第一幀就要是對的方向（BubbleLife 的 LateUpdate 要到這一幀結束才跑）
            float sx = parent.lossyScale.x < 0f ? -1f : 1f;
            float s0 = kind == BubbleKind.Think ? 1f : BubbleLife.PopStart;
            root.transform.localScale = new Vector3(sx * s0, s0, 1f);
            if (kind == BubbleKind.Think) bodyGo.transform.localScale = Vector3.zero;
            return root;
        }

        /// <summary>
        /// 尾巴尖端相對圖中心的 x（世界 px）。置中的尾巴 ≈ 0；斜的尾巴尖端往左（負）。
        /// 數字跟產生器印的「尖端 x」一樣：置中 -0.5、斜 -4（爆炸框 -6）原生 px。
        /// </summary>
        static float TipOffset(Sprite s, bool slanted)
        {
            if (s == null) return 0f;
            if (!slanted) return s.rect.width >= 13 ? 0f : -0.5f * Px;
            return s.rect.width >= 14 ? -6f * Px : -4f * Px;
        }

        static void AddIcon(Transform parent, Sprite icon, Vector3 pos, float scale, int order)
        {
            var i = new GameObject("icon");
            i.transform.SetParent(parent, false);
            i.transform.localPosition = pos;
            i.transform.localScale = new Vector3(scale, scale, 1f);
            var isr = i.AddComponent<SpriteRenderer>();
            isr.sprite = icon;
            isr.sortingOrder = order;
        }

        /// <summary>尺寸對齊：Sliced 至少比兩邊帶寬多 1 px；Tiled 中央要是整數格（至少一格），花樣才接得上。</summary>
        static void Snap(in FrameSpec s, ref int wN, ref int hN)
        {
            if (!s.Tiled)
            {
                wN = Mathf.Max(wN, s.L + s.R + 1);
                hN = Mathf.Max(hN, s.T + s.B + 1);
                return;
            }
            int cx = Mathf.Max(1, Mathf.CeilToInt((wN - s.L - s.R) / (float)s.P));
            int cy = Mathf.Max(1, Mathf.CeilToInt((hN - s.T - s.B) / (float)s.PV));
            wN = s.L + s.R + cx * s.P;
            hN = s.T + s.B + cy * s.PV;
        }

        // ──────────── 圖（Resources/bubbles8/，程式建 Sprite）────────────

        const string ArtDir = "bubbles8/";
        /// <summary>1 原生像素顯示成 Px 世界 px ＝ PPU 1/Px。</summary>
        const float ArtPpu = 1f / Px;

        static readonly Dictionary<string, Sprite> sprites = new();
        static readonly HashSet<Sprite> glyphSet = new();
        static int artState;          // 0 還沒試、1 有、-1 沒有

        static bool ArtReady()
        {
            if (artState == 0)
            {
                bool ok = true;
                foreach (var f in Frames)
                    if (FrameSprite(f) == null) { ok = false; break; }
                artState = ok ? 1 : -1;
                if (!ok) Debug.LogWarning("[SpeechBubble] 找不到 Resources/bubbles8 的泡泡圖（跑 python tools/gen_bubble_art.py），先用舊的泡泡");
                else foreach (BubbleGlyph g in System.Enum.GetValues(typeof(BubbleGlyph)))
                {
                    var s = Spr(GlyphName(g), new Vector2(0.5f, 0.5f));
                    if (s != null) glyphSet.Add(s);
                }
            }
            return artState > 0;
        }

        static bool IsGlyph(Sprite s) => s != null && glyphSet.Contains(s);

        static Sprite FrameSprite(in FrameSpec f)
        {
            string key = "frame-" + f.Name;
            if (sprites.TryGetValue(key, out var sp)) return sp;
            var tex = Resources.Load<Texture2D>(ArtDir + key);
            if (tex != null)
                // 九宮格邊界：Vector4(左, 下, 右, 上)；Tiled 一定要 FullRect
                sp = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0f), ArtPpu,
                                   0, SpriteMeshType.FullRect, new Vector4(f.L, f.B, f.R, f.T));
            sprites[key] = sp;
            return sp;
        }

        static Sprite Spr(string name, Vector2 pivot)
        {
            if (sprites.TryGetValue(name, out var sp)) return sp;
            var tex = Resources.Load<Texture2D>(ArtDir + name);
            if (tex != null)
                sp = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), pivot, ArtPpu, 0, SpriteMeshType.FullRect);
            sprites[name] = sp;      // 找不到也記下來（null），不會每次重試
            return sp;
        }

        // ──────────── 舊版 ────────────

        static GameObject BuildLegacy(Transform parent, float headHeight, Sprite icon, string text, Color32 bg, float life)
        {
            var font = UI.CjkFont.Get();
            string body = Layout(text, font, out float textW, out int lines);
            float iconW = icon != null ? IconSpace : 0f;
            float w = Mathf.Max(MinW, textW + PadX * 2f + iconW);
            float h = H1 + (lines - 1) * LineH;

            var b = new GameObject("bubble");
            b.transform.SetParent(parent, false);
            // 底緣固定在頭頂上方 7px → 變高時往上長，不會壓到頭（根物件在底緣，彈出時從底下長大）
            float baseY = headHeight + 7f;
            b.transform.localPosition = new Vector3(0f, baseY, 0f);

            int seq = BubbleLife.NextSeq();
            int order = 9500 + (seq % 30) * 3;

            var content = new GameObject("body");
            content.transform.SetParent(b.transform, false);
            content.transform.localPosition = new Vector3(0f, h / 2f, 0f);

            var back = new GameObject("bg");
            back.transform.SetParent(content.transform, false);
            var bsr = back.AddComponent<SpriteRenderer>();
            bsr.sprite = RoundRect();
            bsr.drawMode = SpriteDrawMode.Sliced;
            bsr.size = new Vector2(w, h);
            bsr.color = bg;
            bsr.sortingOrder = order;

            if (icon != null)
            {
                // 圖示最長邊 32px；8-bit 道具圖四周有透明邊，經 ItemIconWorld 放到約 38px，看起來才一樣大
                float k = GameArt.ItemIconWorld(32f) / Mathf.Max(icon.rect.width, icon.rect.height);
                AddIcon(content.transform, icon, new Vector3(-w / 2f + 24f, 0f, 0f), k, order + 1);
            }

            float textX = -w / 2f + PadX + iconW + textW / 2f;
            MakeText(content.transform, body, font, new Vector3(textX, 0f, 0f), order + 2);

            var geo = new BubbleLife.Geometry
            {
                Body = content.transform, W = w, BodyBottom = 0f, BodyTop = h, BodyY0 = h / 2f, TailBelow = 0f,
                Pixel = false,
            };
            b.AddComponent<BubbleLife>().Init(parent, life, baseY, seq, geo);

            float sx = parent.lossyScale.x < 0f ? -1f : 1f;
            b.transform.localScale = new Vector3(sx * BubbleLife.PopStart, BubbleLife.PopStart, 1f);
            return b;
        }

        // ──────────── 排版 ────────────

        /// <summary>
        /// 決定文字要不要拆行（最多三行），回傳實際要畫的字串（可能含 \n）、最寬那行的寬度與行數。
        /// 呼叫端自己放了 \n 就照它的。
        /// </summary>
        static string Layout(string text, Font font, out float width, out int lines)
        {
            if (text.IndexOf('\n') >= 0)
            {
                var parts = text.Split('\n');
                width = 0f;
                foreach (var p in parts) width = Mathf.Max(width, Measure(p, font));
                lines = parts.Length;
                return text;
            }

            float full = Measure(text, font);
            if (full <= MaxLineW || text.Length < 4)
            {
                width = full; lines = 1;
                return text;
            }

            // 兩行裝得下就兩行；真的太長（> 兩行寬）才拆三行
            if (full <= MaxLineW * 2f || text.Length < 6)
            {
                int best = BestBreak(text, 0, text.Length, font, out _);
                if (best < 0) { width = full; lines = 1; return text; }
                string s1 = text.Substring(0, best).TrimEnd();
                string s2 = text.Substring(best).TrimStart();
                width = Mathf.Max(Measure(s1, font), Measure(s2, font));
                lines = 2;
                return s1 + "\n" + s2;
            }

            // 三行：先切第一刀（讓三行裡最長的那行最短），第二刀交給 BestBreak
            int bi = -1, bj = -1;
            float bestScore = float.MaxValue;
            for (int i = 1; i < text.Length - 1; i++)
            {
                if (!CanBreak(text, i)) continue;
                float l1 = Measure(text.Substring(0, i).TrimEnd(), font);
                if (l1 > MaxLineW * 1.15f) break;
                int j = BestBreak(text, i, text.Length, font, out float rest);
                if (j < 0) continue;
                float score = Mathf.Max(l1, rest);
                if (IsBreakAfter(text[i - 1]) || text[i - 1] == ' ') score -= Em * 1.5f;
                if (score < bestScore) { bestScore = score; bi = i; bj = j; }
            }
            if (bi < 0) { width = full; lines = 1; return text; }
            string a = text.Substring(0, bi).TrimEnd();
            string b = text.Substring(bi, bj - bi).Trim();
            string c = text.Substring(bj).TrimStart();
            width = Mathf.Max(Measure(a, font), Mathf.Max(Measure(b, font), Measure(c, font)));
            lines = 3;
            return a + "\n" + b + "\n" + c;
        }

        /// <summary>
        /// 在 text[from, to) 裡找一個切點：讓兩段裡比較長的那段盡量短；標點後面、空白處優先，
        /// 不要切在英數字中間（「+120」「3 件」這種被切開很難讀），第二段也不要用標點開頭。
        /// score 回傳兩段裡比較長的那段的寬。找不到回 -1。
        /// </summary>
        static int BestBreak(string text, int from, int to, Font font, out float score)
        {
            int best = -1;
            float bestScore = float.MaxValue;
            score = 0f;
            for (int i = from + 1; i < to; i++)
            {
                if (!CanBreak(text, i)) continue;
                float l1 = Measure(text.Substring(from, i - from).Trim(), font);
                float l2 = Measure(text.Substring(i, to - i).Trim(), font);
                float sc = Mathf.Max(l1, l2);
                float biased = sc;
                if (IsBreakAfter(text[i - 1]) || text[i - 1] == ' ') biased -= Em * 1.5f;    // 偏好在標點／空白後面斷
                if (biased < bestScore) { bestScore = biased; best = i; score = sc; }
            }
            return best;
        }

        static bool CanBreak(string text, int i)
        {
            char a = text[i - 1], c = text[i];
            if (IsAsciiWord(a) && IsAsciiWord(c)) return false;
            return !IsClosingPunct(c);
        }

        static bool IsAsciiWord(char c) => c < 0x80 && (char.IsLetterOrDigit(c) || c == '+' || c == '-');
        static bool IsClosingPunct(char c) => "，。、！？…～）」』,.!?".IndexOf(c) >= 0;
        static bool IsBreakAfter(char c) => "，。、！？…～,.!?".IndexOf(c) >= 0;

        /// <summary>
        /// 一行字在世界上有多寬（px）。優先量字型的 advance；字型還沒準備好就用估的
        /// （全形字 1 em、半形 0.55 em）。
        ///
        /// ⚠️ 動態字型要先 RequestCharactersInTexture 才拿得到 CharacterInfo；拿不到（例如字型裡沒有那個字）
        ///    就退回估算，寧可泡泡寬一點也不要字凸出去。
        /// </summary>
        static float Measure(string s, Font font)
        {
            if (string.IsNullOrEmpty(s)) return 0f;
            bool canMeasure = font != null && font.dynamic;
            if (canMeasure) font.RequestCharactersInTexture(s, FontSize);

            float px = 0f;
            foreach (char ch in s)
            {
                if (canMeasure && font.GetCharacterInfo(ch, out var ci, FontSize) && ci.advance > 0)
                    px += ci.advance * CharSize / 10f;
                else
                    px += Estimate(ch);
            }
            return px;
        }

        static float Estimate(char ch)
        {
            if (ch == ' ') return Em * 0.3f;
            return ch >= 0x2E80 || (ch >= 0xFF00 && ch <= 0xFFEF) ? Em : Em * 0.55f;
        }

        static TextMesh MakeText(Transform parent, string str, Font font, Vector3 localPos, int order)
        {
            var go = new GameObject("text");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos + new Vector3(0f, 0f, -0.01f);

            var tm = go.AddComponent<TextMesh>();
            tm.text = str;
            tm.fontSize = FontSize;
            tm.characterSize = CharSize;
            tm.lineSpacing = 0.85f;          // 多行時行距收一點（≈ LineH 20px）
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color32(240, 236, 228, 255);

            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = order;
            return tm;
        }

        static Sprite roundRect;

        /// <summary>舊版的圓角矩形底圖（程式生成一次，之後共用）。九宮格邊界設在圓角外。</summary>
        static Sprite RoundRect()
        {
            if (roundRect != null) return roundRect;

            int n = Radius * 2 + 4;                     // 剛好容得下兩個圓角 + 中間 4px
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    // 距離最近角落的圓心多遠 —— 在半徑內就是不透明
                    float cx = Mathf.Clamp(x, Radius, n - 1 - Radius);
                    float cy = Mathf.Clamp(y, Radius, n - 1 - Radius);
                    float d = Vector2.Distance(new Vector2(x, y), new Vector2(cx, cy));
                    float a = Mathf.Clamp01(Radius - d + 0.5f);      // 邊緣抗鋸齒
                    tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
                }
            tex.Apply();

            roundRect = Sprite.Create(tex, new Rect(0, 0, n, n), new Vector2(0.5f, 0.5f), 1f,
                                      0, SpriteMeshType.FullRect,
                                      new Vector4(Radius, Radius, Radius, Radius));   // 九宮格邊界
            return roundRect;
        }
    }

    /// <summary>
    /// 掛在每一顆對話泡上：管它的生命週期（彈出 → 停留 → 縮小淡出 → 銷毀）、
    /// 每幀把鏡像反轉回來、跟附近的泡泡錯開高度、不跑出畫面、尾巴對準說話的人。
    ///
    /// ⚠️ 泡泡是角色的子物件 —— 角色被 Destroy 時泡泡一起走（OnDestroy 會把自己從清單拿掉），
    ///    呼叫端不用另外清。
    /// ⚠️ 開著視窗（UIState.ModalOpen）時整個遊戲是停的，泡泡的計時也跟著停，
    ///    不然關掉視窗時顧客還站在原地、話卻已經講完了。
    /// ⚠️ LateUpdate 裡不配置任何記憶體（每幀都跑，客人一多就是好幾顆）。
    /// </summary>
    public class BubbleLife : MonoBehaviour
    {
        /// <summary>彈出動畫的起始縮放。</summary>
        public const float PopStart = 0.6f;
        /// <summary>彈出時間（含回彈）。</summary>
        const float PopTime = 0.16f;
        /// <summary>EaseOutBack 的回彈係數：2.4 ≈ 最大到 1.06 倍再落回 1。</summary>
        const float PopBack = 2.4f;
        const float FadeTime = 0.3f;
        /// <summary>錯開時兩顆泡泡之間留幾 px（另外還會加上尾巴伸出去的長度）。</summary>
        const float Gap = 4f;
        /// <summary>最多往上抬多少（再多就乾脆疊著，總比飛到天花板上好）。</summary>
        const float MaxLift = 150f;
        /// <summary>離畫面邊緣至少留多少 px。</summary>
        const float EdgeMargin = 6f;
        /// <summary>想事情：小圓點一顆顆出來的間隔、雲朵本體什麼時候開始彈出。</summary>
        const float DotStep = 0.05f, ThinkBodyDelay = 0.12f;
        /// <summary>想事情：小圓點那一串的終點（雲底）往旁邊歪多少 px。</summary>
        const float DotLean = 9f;

        /// <summary>建泡泡時算好、交給 BubbleLife 的幾何（根物件座標，世界 px，原點＝尾巴尖端）。</summary>
        public struct Geometry
        {
            public Transform Body;
            public float W;
            /// <summary>看得到的本體下緣／上緣（不含落影）。</summary>
            public float BodyBottom, BodyTop;
            /// <summary>本體的原點 y（細畫版＝樣板底邊；舊版＝中心）。</summary>
            public float BodyY0;
            /// <summary>尾巴從本體下緣往下伸多長（疊泡泡時要讓出這段）。</summary>
            public float TailBelow;
            public SpriteRenderer Tail;
            public Sprite TailC, TailS;
            public float TailTipC, TailTipS, TailInset;
            /// <summary>想事情的三顆小圓點（小、中、大）；其他樣式 null。</summary>
            public SpriteRenderer[] Dots;
            public bool Pixel;
        }

        static readonly List<BubbleLife> live = new();
        static int seqCounter;

        /// <summary>給下一顆泡泡的序號（越大越新）。</summary>
        public static int NextSeq() => ++seqCounter;

        Transform owner;
        float life, age;
        float baseY;
        float lift, bx;
        int seq;
        Geometry g;
        SpriteRenderer[] srs;
        TextMesh[] tms;
        Color[] srBase, tmBase;

        public void Init(Transform owner, float life, float baseY, int seq, Geometry geo)
        {
            this.owner = owner; this.life = life;
            this.baseY = baseY; this.seq = seq;
            g = geo;
            srs = GetComponentsInChildren<SpriteRenderer>(true);
            tms = GetComponentsInChildren<TextMesh>(true);
            srBase = new Color[srs.Length];
            for (int i = 0; i < srs.Length; i++) srBase[i] = srs[i].color;
            tmBase = new Color[tms.Length];
            for (int i = 0; i < tms.Length; i++) tmBase[i] = tms[i].color;
            live.Add(this);
        }

        void OnEnable() { if (owner != null && !live.Contains(this)) live.Add(this); }
        void OnDestroy() { live.Remove(this); }
        void OnDisable() { live.Remove(this); }   // Clear 會先 SetActive(false) —— 不要再擋別人的位置

        /// <summary>這顆泡泡的本體現在在世界上佔的矩形（錯開用；含往下伸的尾巴，新的泡泡才不會把尾巴戳進舊的裡面）。</summary>
        Rect WorldRect(float withLift, float withBx)
        {
            var p = owner != null ? owner.position : transform.position;
            float y0 = p.y + baseY + withLift + g.BodyBottom - g.TailBelow;
            float y1 = p.y + baseY + withLift + g.BodyTop;
            return new Rect(p.x + withBx - g.W / 2f, y0, g.W, y1 - y0);
        }

        void LateUpdate()
        {
            if (owner == null) return;
            float dt = UIState.ModalOpen ? 0f : Time.deltaTime;
            age += dt;

            // ① 生命週期：時間到就縮小淡出、銷毀
            float fade = 1f;
            if (life > 0f)
            {
                if (age >= life) { Destroy(gameObject); return; }
                fade = Mathf.Clamp01((life - age) / FadeTime);
            }
            SetAlpha(fade);

            // ② 不跑出畫面：本體左右夾在攝影機看得到的範圍裡（尾巴另外對準說話的人）
            var op = owner.position;
            var cam = Camera.main;
            float camTop = float.MaxValue;
            bx = 0f;
            if (cam != null && cam.orthographic)
            {
                float halfH = cam.orthographicSize, halfW = halfH * cam.aspect;
                var cp = cam.transform.position;
                float lo = cp.x - halfW + EdgeMargin + g.W / 2f;
                float hi = cp.x + halfW - EdgeMargin - g.W / 2f;
                if (lo <= hi) bx = Mathf.Clamp(op.x, lo, hi) - op.x;
                camTop = cp.y + halfH - EdgeMargin;
            }

            // ③ 錯開：只讓「比我新的」讓「比我舊的」—— 舊的不動，畫面才穩定，不會兩顆互相推來推去。
            //    比較的是對方**目前的**位置（它這一幀可能還沒更新，差一幀看不出來）。
            float target = 0f;
            for (int pass = 0; pass < 4; pass++)
            {
                bool moved = false;
                var me = WorldRect(target, bx);
                for (int k = 0; k < live.Count; k++)
                {
                    var o = live[k];
                    if (o == this || o.seq > seq || o.owner == null || o.owner == owner) continue;
                    var r = o.WorldRect(o.lift, o.bx);
                    // 對方的矩形含它的尾巴；我的底緣（含尾巴）要在它本體的頂上
                    float rTop = r.yMax;
                    bool xHit = me.xMin < r.xMax + Gap && r.xMin < me.xMax + Gap;
                    bool yHit = me.yMin < rTop + Gap && r.yMin < me.yMax + Gap;
                    if (!xHit || !yHit) continue;
                    float need = rTop + Gap - (me.yMin - target);
                    if (need > target) { target = need; moved = true; me = WorldRect(target, bx); }
                }
                if (!moved) break;
            }
            target = Mathf.Min(target, MaxLift);
            // 頂端不要超出畫面：往下壓（最多壓到蓋住頭頂一點點 —— 總比看不到好）
            float top = op.y + baseY + target + g.BodyTop;
            if (top > camTop) target = Mathf.Max(target - (top - camTop), -baseY * 0.35f);

            // 平滑移動（舊泡泡消失後往下落回原位也一樣），速度夠快，看起來像「讓開」而不是飄
            //    第一幀直接就位（剛冒出來就從別人身上滑上去很怪）
            lift = age <= dt ? target : Mathf.MoveTowards(lift, target, 400f * dt);

            // ④ 縮放：彈出（EaseOutBack）＋結束時縮小；依父物件目前的翻面狀態反轉回來
            //    ⚠️ 用 lossyScale 而不是 localScale：就算以後角色又被包進一個翻面的父物件，也一樣對。
            bool think = g.Dots != null;
            float shrink = 0.85f + 0.15f * fade;
            float rootS = (think ? 1f : Pop(age)) * shrink;
            float sx = owner.lossyScale.x < 0f ? -1f : 1f;
            transform.localScale = new Vector3(sx * rootS, rootS, 1f);

            // 輕輕上下浮（整數 px 的兩段，像素圖才不會糊糊地抖）；每顆相位錯開
            float bob = g.Pixel ? Mathf.Round(Mathf.Sin(age * 2.6f + seq * 1.7f) * 0.8f) : 0f;
            var lp = transform.localPosition;
            transform.localPosition = new Vector3(0f, baseY + lift + bob, lp.z);

            if (g.Body != null)
            {
                g.Body.localPosition = new Vector3(bx, g.BodyY0, 0f);
                if (think)
                {
                    float t = age - ThinkBodyDelay;
                    float s = t < 0f ? 0f : Pop(t);
                    g.Body.localScale = new Vector3(s, s, 1f);
                }
            }

            // ⑤ 尾巴對準說話的人（根物件原點 x = 0 就是他）
            if (g.Pixel) AimTail(think);
        }

        void AimTail(bool think)
        {
            float minX = bx - g.W / 2f + g.TailInset, maxX = bx + g.W / 2f - g.TailInset;
            if (minX > maxX) minX = maxX = bx;
            if (think)
            {
                // 三顆小圓點：從本體底邊（夾在可以接的範圍內）連到頭頂，小的靠頭、大的靠雲
                // 往雲的中間斜上去一點（像一串冒上去的泡泡），但不超出可以接的範圍
                float ax = Mathf.Clamp(bx >= 0f ? DotLean : -DotLean, minX, maxX), ay = g.BodyBottom - 1f;
                for (int i = 0; i < g.Dots.Length; i++)
                {
                    var d = g.Dots[i];
                    if (d == null) continue;
                    d.enabled = age >= i * DotStep;
                    float f = i == 0 ? 0.1f : i == 1 ? 0.4f : 0.74f;        // 0＝頭頂、1＝雲的底邊
                    d.transform.localPosition = new Vector3(ax * f, ay * f + 2f, 0f);
                }
                return;
            }
            if (g.Tail == null) return;
            float tx;
            if (Mathf.Abs(bx) < 3f || g.TailS == null)
            {
                g.Tail.sprite = g.TailC;
                g.Tail.flipX = false;
                tx = Mathf.Clamp(-g.TailTipC, minX, maxX);
            }
            else
            {
                // 泡泡被推開了：換斜的尾巴，尖端歪向說話的人（圖本身尖端朝左，人在右邊就翻過來）
                bool speakerRight = bx < 0f;
                g.Tail.sprite = g.TailS;
                g.Tail.flipX = speakerRight;
                float tip = speakerRight ? -g.TailTipS : g.TailTipS;
                tx = Mathf.Clamp(-tip, minX, maxX);
            }
            var tp = g.Tail.transform.localPosition;
            g.Tail.transform.localPosition = new Vector3(tx, tp.y, tp.z);
        }

        /// <summary>0.6 起跳、EaseOutBack 回彈一點點再落到 1（同 gen_bubble_art.py 的 pop_scale）。</summary>
        static float Pop(float t)
        {
            if (t >= PopTime) return 1f;
            float x = t / PopTime - 1f;
            float e = 1f + (PopBack + 1f) * x * x * x + PopBack * x * x;
            return PopStart + (1f - PopStart) * e;
        }

        float lastAlpha = 1f;

        void SetAlpha(float a)
        {
            if (Mathf.Approximately(a, lastAlpha)) return;
            lastAlpha = a;
            for (int i = 0; i < srs.Length; i++)
                if (srs[i] != null) { var c = srBase[i]; c.a *= a; srs[i].color = c; }
            for (int i = 0; i < tms.Length; i++)
                if (tms[i] != null) { var c = tmBase[i]; c.a *= a; tms[i].color = c; }
        }
    }
}
