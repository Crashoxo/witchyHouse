using System.Collections.Generic;
using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 世界空間的對話泡：圓角底 ＋（可選）道具圖示 ＋ 文字。
    /// 顧客進門招呼、想買什麼、成交了沒、只逛不買的評論都用它。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// Cocos 版用 Graphics 即時畫圓角矩形（roundRect + fill + stroke），還要手畫小尾巴。
    /// Unity 沒有等價的即時繪圖元件，所以底圖是**程式生成的九宮格 Sprite**（生一次快取）——
    /// 換句話說圓角是烤進貼圖的，用 sliced 模式撐開，任何尺寸都不會變形。
    ///
    /// ⚠️ 文字用 TextMesh 不是 TextMeshPro —— 同 GatherTree 的理由：TextMesh 吃得下
    ///    作業系統的動態字型，中文不用先烘 FontAsset。
    ///
    /// ── 11/26 改版 ─────────────────────────────────────────────
    /// 原本固定 150×46、永遠掛著直到被下一個蓋掉。顧客開始會聊天之後句子變長、人也變多，所以：
    ///   ① **寬度依文字長度決定**（量字型的 advance），超過 <see cref="MaxLineW"/> 就拆成兩行。
    ///   ② **存在時間**：life &gt; 0 的泡泡幾秒後自己淡出消失（life = 0 ＝ 跟舊版一樣一直掛著）。
    ///   ③ **重疊錯開**：多位顧客站在一起時，新的泡泡會往上抬到不壓住舊的（見 <see cref="BubbleLife"/>）。
    ///   ④ **翻面修正**：舊版只在 Show 的那一刻看角色有沒有翻面 —— 泡泡顯示中角色轉身
    ///      （例如成交後轉向門口走）文字就會變鏡像。現在改成每幀依父物件的 lossyScale 反轉回來。
    /// </summary>
    public static class SpeechBubble
    {
        /// <summary>單行泡泡的高度（跟舊版一樣）。</summary>
        const float H1 = 46f;
        /// <summary>第二行多出來的高度。⚠️ 要跟 TextMesh 的 lineSpacing 對得上（見 MakeText）。</summary>
        const float LineH = 20f;
        /// <summary>泡泡最窄多寬（「+12」這種短字也不要縮成一顆小豆子）。</summary>
        const float MinW = 64f;
        /// <summary>一行文字最寬多少 px，超過就拆兩行（≈ 12 個中文字）。</summary>
        const float MaxLineW = 196f;
        /// <summary>文字左右的留白。</summary>
        const float PadX = 14f;
        /// <summary>有圖示時，圖示佔掉的寬度（圖示本身 ≈38px ＋ 間距）。</summary>
        const float IconSpace = 40f;
        const int Radius = 12;

        // 字級：TextMesh 的世界大小 ≈ fontSize × characterSize ÷ 10（見 GatherTree 的換算說明）
        const int FontSize = 36;
        const float CharSize = 4.5f;          // ≈ 16px 高
        const float Em = FontSize * CharSize / 10f;

        /// <summary>
        /// 在 parent 頭頂 headHeight 的地方掛一個對話泡（會先移除舊的）。
        /// </summary>
        /// <param name="parent">要掛在誰身上</param>
        /// <param name="headHeight">這個角色的顯示高度（泡泡擺在它上方）</param>
        /// <param name="icon">左邊的小圖示（null＝只有文字）</param>
        /// <param name="text">內容（太長會自動拆兩行；也可以自己放 \n）</param>
        /// <param name="bg">底色</param>
        /// <param name="life">幾秒後自動淡出消失；0 ＝ 一直掛著（舊版行為，直到被下一個蓋掉或 Clear）</param>
        public static GameObject Show(Transform parent, float headHeight,
                                      Sprite icon, string text, Color32 bg, float life = 0f)
        {
            Clear(parent);
            text ??= "";

            // ── 排版：先量字，決定要不要拆行、泡泡多寬 ──
            var font = UI.CjkFont.Get();
            string body = Layout(text, font, out float textW, out int lines);
            float iconW = icon != null ? IconSpace : 0f;
            float w = Mathf.Max(MinW, textW + PadX * 2f + iconW);
            float h = H1 + (lines - 1) * LineH;

            var b = new GameObject("bubble");
            b.transform.SetParent(parent, false);
            // 底緣固定在頭頂上方 7px（＝舊版 46 高、中心在 +30 的底緣）→ 變高時往上長，不會壓到頭
            float baseY = headHeight + 7f + h / 2f;
            b.transform.localPosition = new Vector3(0f, baseY, 0f);

            // 排序：新的泡泡畫在舊的上面（重疊錯開之前的那一兩幀、或錯開失敗時才看得出差別）。
            // ⚠️ 上限要停在 9600 以下 —— 成交的表情動畫是 9600，要蓋在泡泡上面。
            int seq = BubbleLife.NextSeq();
            int order = 9500 + (seq % 30) * 3;

            var back = new GameObject("bg");
            back.transform.SetParent(b.transform, false);
            var bsr = back.AddComponent<SpriteRenderer>();
            bsr.sprite = RoundRect();
            bsr.drawMode = SpriteDrawMode.Sliced;
            bsr.size = new Vector2(w, h);
            bsr.color = bg;
            bsr.sortingOrder = order;

            if (icon != null)
            {
                var i = new GameObject("icon");
                i.transform.SetParent(b.transform, false);
                // 圖示最長邊 32px；8-bit 道具圖四周有透明邊，經 ItemIconWorld 放到約 38px，看起來才一樣大
                float k = GameArt.ItemIconWorld(32f) / Mathf.Max(icon.rect.width, icon.rect.height);
                i.transform.localPosition = new Vector3(-w / 2f + 24f, 0f, 0f);
                i.transform.localScale = new Vector3(k, k, 1f);
                var isr = i.AddComponent<SpriteRenderer>();
                isr.sprite = icon;
                isr.sortingOrder = order + 1;
            }

            // 文字置中在「扣掉圖示之後」的那塊
            float textX = -w / 2f + PadX + iconW + textW / 2f;
            MakeText(b.transform, body, font, new Vector3(textX, 0f, 0f), order + 2);

            // 生命週期 ＋ 每幀反轉鏡像 ＋ 重疊錯開，全部交給這個元件
            b.AddComponent<BubbleLife>().Init(parent, life, w, h, baseY, seq);

            // 第一幀就要是對的方向（BubbleLife 的 LateUpdate 要到這一幀結束才跑）
            float sx = parent.lossyScale.x < 0f ? -1f : 1f;
            b.transform.localScale = new Vector3(sx * BubbleLife.PopStart, BubbleLife.PopStart, 1f);
            return b;
        }

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

        // ──────────── 排版 ────────────

        /// <summary>
        /// 決定文字要不要拆兩行，回傳實際要畫的字串（可能含一個 \n）、最寬那行的寬度與行數。
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

            // 找一個切點：讓兩行裡比較長的那行盡量短；標點後面、空白處優先，
            // 不要切在英數字中間（「+120」「3 件」這種被切開很難讀），第二行也不要用標點開頭。
            int best = -1;
            float bestScore = float.MaxValue;
            for (int i = 1; i < text.Length; i++)
            {
                char a = text[i - 1], c = text[i];
                if (IsAsciiWord(a) && IsAsciiWord(c)) continue;
                if (IsClosingPunct(c)) continue;
                float l1 = Measure(text.Substring(0, i).TrimEnd(), font);
                float l2 = Measure(text.Substring(i).TrimStart(), font);
                float score = Mathf.Max(l1, l2);
                if (IsBreakAfter(a) || a == ' ') score -= Em * 1.5f;    // 偏好在標點／空白後面斷
                if (score < bestScore) { bestScore = score; best = i; }
            }
            if (best < 0) { width = full; lines = 1; return text; }

            string s1 = text.Substring(0, best).TrimEnd();
            string s2 = text.Substring(best).TrimStart();
            width = Mathf.Max(Measure(s1, font), Measure(s2, font));
            lines = 2;
            return s1 + "\n" + s2;
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

        static void MakeText(Transform parent, string str, Font font, Vector3 localPos, int order)
        {
            var go = new GameObject("text");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos + new Vector3(0f, 0f, -0.01f);

            var tm = go.AddComponent<TextMesh>();
            tm.text = str;
            tm.fontSize = FontSize;
            tm.characterSize = CharSize;
            tm.lineSpacing = 0.85f;          // 兩行時行距收一點（≈ LineH 20px）
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color32(240, 236, 228, 255);

            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = order;
        }

        static Sprite roundRect;

        /// <summary>圓角矩形底圖（程式生成一次，之後共用）。九宮格邊界設在圓角外。</summary>
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
    /// 掛在每一顆對話泡上：管它的生命週期（彈出 → 停留 → 淡出 → 銷毀）、
    /// 每幀把鏡像反轉回來、以及跟附近的泡泡錯開高度。
    ///
    /// ⚠️ 泡泡是角色的子物件 —— 角色被 Destroy 時泡泡一起走（OnDestroy 會把自己從清單拿掉），
    ///    呼叫端不用另外清。
    /// ⚠️ 開著視窗（UIState.ModalOpen）時整個遊戲是停的，泡泡的計時也跟著停，
    ///    不然關掉視窗時顧客還站在原地、話卻已經講完了。
    /// </summary>
    public class BubbleLife : MonoBehaviour
    {
        /// <summary>彈出動畫的起始縮放。</summary>
        public const float PopStart = 0.6f;
        const float PopTime = 0.12f;
        const float FadeTime = 0.35f;
        /// <summary>錯開時兩顆泡泡之間留幾 px。</summary>
        const float Gap = 4f;
        /// <summary>最多往上抬多少（再多就乾脆疊著，總比飛到天花板上好）。</summary>
        const float MaxLift = 150f;

        static readonly List<BubbleLife> live = new();
        static int seqCounter;

        /// <summary>給下一顆泡泡的序號（越大越新）。</summary>
        public static int NextSeq() => ++seqCounter;

        Transform owner;
        float life, age;
        float w, h, baseY;
        float lift;
        int seq;
        SpriteRenderer[] srs;
        TextMesh[] tms;
        Color[] srBase, tmBase;

        public void Init(Transform owner, float life, float w, float h, float baseY, int seq)
        {
            this.owner = owner; this.life = life;
            this.w = w; this.h = h; this.baseY = baseY; this.seq = seq;
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

        /// <summary>這顆泡泡現在在世界上佔的矩形（錯開用）。</summary>
        Rect WorldRect(float withLift)
        {
            var p = owner != null ? owner.position : transform.position;
            float cy = p.y + baseY + withLift;
            return new Rect(p.x - w / 2f, cy - h / 2f, w, h);
        }

        void LateUpdate()
        {
            if (owner == null) return;
            float dt = UIState.ModalOpen ? 0f : Time.deltaTime;
            age += dt;

            // ① 生命週期：時間到就淡出、銷毀
            if (life > 0f)
            {
                if (age >= life) { Destroy(gameObject); return; }
                float a = Mathf.Clamp01((life - age) / FadeTime);
                if (a < 1f) SetAlpha(a);
            }

            // ② 錯開：只讓「比我新的」讓「比我舊的」—— 舊的不動，畫面才穩定，不會兩顆互相推來推去。
            //    比較的是對方**目前的**位置（它這一幀可能還沒更新，差一幀看不出來）。
            float target = 0f;
            for (int pass = 0; pass < 4; pass++)
            {
                bool moved = false;
                var me = WorldRect(target);
                foreach (var o in live)
                {
                    if (o == this || o.seq > seq || o.owner == null || o.owner == owner) continue;
                    var r = o.WorldRect(o.lift);
                    bool xHit = me.xMin < r.xMax + Gap && r.xMin < me.xMax + Gap;
                    bool yHit = me.yMin < r.yMax + Gap && r.yMin < me.yMax + Gap;
                    if (!xHit || !yHit) continue;
                    float need = r.yMax + Gap - (me.yMin - target);   // 我的底緣要在它頂上
                    if (need > target) { target = need; moved = true; me = WorldRect(target); }
                }
                if (!moved) break;
            }
            target = Mathf.Min(target, MaxLift);
            // 平滑移動（舊泡泡消失後往下落回原位也一樣），速度夠快，看起來像「讓開」而不是飄
            //    第一幀直接就位（剛冒出來就從別人身上滑上去很怪）
            lift = age <= dt ? target : Mathf.MoveTowards(lift, target, 400f * dt);

            // ③ 位置與縮放：彈出動畫 ＋ 依父物件目前的翻面狀態反轉回來
            //    ⚠️ 用 lossyScale 而不是 localScale：就算以後角色又被包進一個翻面的父物件，也一樣對。
            float pop = PopStart + (1f - PopStart) * Mathf.Clamp01(age / PopTime);
            float sx = owner.lossyScale.x < 0f ? -1f : 1f;
            transform.localScale = new Vector3(sx * pop, pop, 1f);
            var lp = transform.localPosition;
            transform.localPosition = new Vector3(0f, baseY + lift, lp.z);
        }

        void SetAlpha(float a)
        {
            for (int i = 0; i < srs.Length; i++)
                if (srs[i] != null) { var c = srBase[i]; c.a *= a; srs[i].color = c; }
            for (int i = 0; i < tms.Length; i++)
                if (tms[i] != null) { var c = tmBase[i]; c.a *= a; tms[i].color = c; }
        }
    }
}
