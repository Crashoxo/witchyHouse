using UnityEngine;
using UnityEngine.UIElements;

namespace WitchShop.UI
{
    /// <summary>
    /// 8-bit 像素風 UI 外觀（木框＋羊皮紙＋紫布金滾邊）的總開關與共用小零件。
    ///
    /// 用法：面板 Build 時，在 `root.styleSheets.Add(原本的樣式表)` **之後**呼叫 <see cref="Apply"/>。
    ///   * 一律掛 `ui/SkinBase.uss` —— 新增元素（金幣＋數字、材料小卡、鍵帽…）的排版，配色是舊的暗木主題。
    ///   * <see cref="Enabled"/> 為 true 時再掛 `ui/Skin8.uss`，並在根上加 `sk` class；Skin8 的每一條規則
    ///     都寫成 `.sk …`，所以**關掉開關＝整套退回舊外觀**（圖檔在 `Resources/ui/skin8/`，由 tools/gen_ui_skin.py 產生）。
    ///
    /// ── 為什麼是「疊一張樣式表」而不是改舊的 ──────────────────────
    /// 舊的 ShopManageStyle／BagPanelStyle／HudStyle 一個字都沒動：Skin8 用 `.sk` 前綴把特異度墊高一階
    /// （`.sk .btn` 贏 `.btn-list`；`.sk .btn:hover` 贏 `.btn-list:hover`），同特異度時後掛的樣式表贏。
    /// 退回只要改 <see cref="Enabled"/> 一個值。
    ///
    /// ⚠️ 用 `static readonly` 不用 `const`：const false 會讓 `if (Enabled)` 後面整段變成「偵測到無法執行的程式碼」警告。
    ///
    /// ⚠️ 程式裡**不要再寫 inline 顏色**（`el.style.color = …`）：inline 的優先權比任何 uss 都高，
    ///    Skin8 把底換成淺色羊皮紙之後，舊的淺色字就蓋不掉、整個看不見。顏色一律給 class。
    /// </summary>
    public static class UiSkin
    {
        /// <summary>總開關：false ＝ 退回舊的純色塊外觀（新增的圖示化元素仍在，只是沒有像素框）。</summary>
        public static readonly bool Enabled = true;

        /// <summary>根上的 class；Skin8.uss 的規則全部以它開頭。</summary>
        public const string RootClass = "sk";

        const string BasePath = "ui/SkinBase";
        const string SkinPath = "ui/Skin8";

        static StyleSheet baseSheet, skinSheet;

        /// <summary>掛上外觀樣式表（重複呼叫沒關係）。要在面板原本的樣式表**之後**呼叫。</summary>
        public static void Apply(VisualElement root)
        {
            if (root == null) return;
            if (baseSheet == null) baseSheet = Resources.Load<StyleSheet>(BasePath);
            if (baseSheet != null && !root.styleSheets.Contains(baseSheet)) root.styleSheets.Add(baseSheet);
            else if (baseSheet == null) Debug.LogWarning($"[UiSkin] 找不到 Resources/{BasePath}.uss");

            if (!Enabled) return;
            if (skinSheet == null) skinSheet = Resources.Load<StyleSheet>(SkinPath);
            if (skinSheet == null)
            {
                // 新 uss 要等 Unity 匯入過才載得到；載不到就維持舊外觀，不要半套
                Debug.LogWarning($"[UiSkin] 找不到 Resources/{SkinPath}.uss —— 維持舊外觀");
                return;
            }
            if (!root.styleSheets.Contains(skinSheet)) root.styleSheets.Add(skinSheet);
            root.AddToClassList(RootClass);
        }

        /// <summary>外觀真的套上了沒（開關開著，且 Skin8.uss 載得到）。</summary>
        public static bool On => Enabled && (skinSheet != null || Resources.Load<StyleSheet>(SkinPath) != null);

        // ── 金幣 ─────────────────────────────────────────────

        /// <summary>金幣小圖（21×21，原尺寸 ＝ 7×7 邏輯格 ×3；舊外觀時寬高 0）。</summary>
        public static VisualElement Coin()
        {
            var c = new VisualElement();
            c.AddToClassList("sk-coin");
            c.pickingMode = PickingMode.Ignore;
            return c;
        }

        /// <summary>
        /// 「金幣圖示＋數字」。外觀關著時數字後面自己帶「 金」—— 圖示寬高是 0，不帶字就看不出是錢。
        /// <paramref name="numClass"/>：額外加在數字上的 class（例如價格要比較大）。
        /// </summary>
        public static VisualElement Money(int amount, string numClass = null)
        {
            var box = new VisualElement();
            box.AddToClassList("sk-money");
            box.pickingMode = PickingMode.Ignore;
            box.Add(Coin());
            var num = new Label(MoneyText(amount));
            num.AddToClassList("sk-money-num");
            if (!string.IsNullOrEmpty(numClass)) num.AddToClassList(numClass);
            num.pickingMode = PickingMode.Ignore;
            box.Add(num);
            return box;
        }

        /// <summary>金額文字：有金幣圖時只寫數字，沒有時寫「12 金」。</summary>
        public static string MoneyText(int amount) => On ? amount.ToString() : $"{amount} 金";

        /// <summary>
        /// 標題列右上角的金幣袋：建一個 [金幣][數字] 的容器，回傳裡面那個數字 Label（每次 Refresh 改它的 text，
        /// 用 <see cref="MoneyText"/> 填）。舊的 `.gold` class 留在 Label 上，舊外觀長得跟以前一樣。
        /// </summary>
        public static VisualElement GoldBox(out Label number)
        {
            var box = new VisualElement();
            box.AddToClassList("gold-box");
            box.Add(Coin());
            number = new Label();
            number.AddToClassList("gold");
            box.Add(number);
            return box;
        }

        /// <summary>
        /// 按鈕裡放「短字＋金幣＋數字」（例如「全賣 [金]84」）。外觀關著時退回原本的整句文字 <paramref name="fallback"/>。
        /// ⚠️ Button 的 text 要設成空字串，不然 Button 自己的文字會跟子元素擠在一起。
        /// </summary>
        public static void MoneyButtonContent(Button b, string word, int amount, string fallback)
        {
            if (!On) { b.text = fallback; return; }
            b.text = "";
            b.AddToClassList("btn-money");
            var w = new Label(word);
            w.AddToClassList("btn-money-text");
            w.pickingMode = PickingMode.Ignore;
            b.Add(w);
            var m = Money(amount);
            b.Add(m);
        }

        // ── 徽章／小圖示 ─────────────────────────────────────

        /// <summary>數量徽章（深木小膠囊＋米色字），例如背包格的「12」、列上的「×3」。</summary>
        public static Label Badge(string text)
        {
            var l = new Label(text);
            l.AddToClassList("sk-badge");
            l.pickingMode = PickingMode.Ignore;
            return l;
        }

        /// <summary>
        /// skin8 裡的固定尺寸小圖（lock／check／heart／heart-off／arrow；第二輪加了 gear／star／basket／sack／leaf／flask／bullet）。
        /// 舊外觀時寬高 0。尺寸寫在 Skin8.uss 的 .sk-ico--名稱。
        /// </summary>
        public static VisualElement Ico(string name)
        {
            var el = new VisualElement();
            el.AddToClassList("sk-ico");
            el.AddToClassList("sk-ico--" + name);
            el.pickingMode = PickingMode.Ignore;
            return el;
        }

        /// <summary>「道具小圖＋文字」：例如「收成 [花]×3」。小圖 24×24（道具圖示的邏輯 1:1，最銳利）。</summary>
        public static VisualElement IconCount(Sprite sp, string text)
        {
            var box = new VisualElement();
            box.AddToClassList("sk-iconcount");
            box.pickingMode = PickingMode.Ignore;
            var ic = new VisualElement();
            ic.AddToClassList("sk-iconcount-icon");
            if (sp != null) ic.style.backgroundImage = new StyleBackground(sp);
            box.Add(ic);
            var l = new Label(text);
            l.AddToClassList("sk-iconcount-text");
            box.Add(l);
            return box;
        }

        /// <summary>
        /// 交錯列：容器裡帶 `row` class 的子元素，奇數列加 `sk-alt`（換一張稍深的卡片底）。
        /// USS 沒有 :nth-child，只能在填完列之後由程式標。
        /// </summary>
        public static void Stripe(VisualElement container)
        {
            if (container == null) return;
            int i = 0;
            foreach (var c in container.Children())
            {
                if (!c.ClassListContains("row")) continue;
                c.EnableInClassList("sk-alt", (i++ & 1) == 1);
            }
        }

        // ── 底部：鍵帽＋極短字 ───────────────────────────────

        /// <summary>鍵帽（「Esc」「Tab」這種），米白小鍵＋深色字。</summary>
        public static Label KeyCap(string key)
        {
            var k = new Label(key);
            k.AddToClassList("sk-key");
            k.pickingMode = PickingMode.Ignore;
            return k;
        }

        /// <summary>
        /// 在面板最底下加一條分隔線＋一列「[Esc] 關閉 ……… 資訊」，回傳右邊的資訊 Label（可能留空）。
        /// 取代原本「Esc 關閉 · 一長串說明」的 hint：能用圖表達的不用句子。
        /// <paramref name="keys"/>：要畫成鍵帽的按鍵（例如 "Esc" 或 "Tab", "Esc"），<paramref name="action"/>：鍵帽後面的短字。
        /// </summary>
        public static Label Footer(VisualElement panel, string action, params string[] keys)
        {
            var div = new VisualElement();
            div.AddToClassList("sk-divider");
            div.pickingMode = PickingMode.Ignore;
            panel.Add(div);

            var row = new VisualElement();
            row.AddToClassList("sk-footer");
            row.pickingMode = PickingMode.Ignore;
            panel.Add(row);
            AddKeys(row, action, keys);

            var spacer = new VisualElement();
            spacer.style.flexGrow = 1;
            row.Add(spacer);

            var info = new Label();
            info.AddToClassList("sk-foot-info");
            row.Add(info);
            return info;
        }

        /// <summary>把「[鍵][鍵] 短字」加到一列的最前面（BagPanel 的底列是 UXML 現成的，用這支插進去）。</summary>
        public static void AddKeys(VisualElement row, string action, params string[] keys)
        {
            int at = 0;
            foreach (var k in keys) row.Insert(at++, KeyCap(k));
            var t = new Label(action);
            t.AddToClassList("sk-foot-text");
            t.pickingMode = PickingMode.Ignore;
            row.Insert(at, t);
        }

        // ── 浮動說明（UI Toolkit 執行期沒有 tooltip，自己做）────────

        /// <summary>
        /// 在 <paramref name="host"/>（通常是面板本身）裡建一個浮動說明 Label，預設隱藏。
        /// ⚠️ `VisualElement.tooltip` 只在編輯器裡會顯示，遊戲執行期不會畫 —— 所以自己做。
        /// </summary>
        public static Label MakeTip(VisualElement host)
        {
            var tip = new Label();
            tip.AddToClassList("sk-tip");
            tip.pickingMode = PickingMode.Ignore;     // 不能擋到底下的滑鼠，不然會一直 Enter/Leave 閃爍
            host.Add(tip);
            return tip;
        }

        /// <summary>
        /// 滑鼠移到 <paramref name="target"/> 上時，在它正下方顯示 <paramref name="text"/>；移開就收起來。
        /// 位置用 worldBound 換算到 host 座標（ScrollView 捲動、面板縮放動畫都已經算進 worldBound）。
        /// <paramref name="above"/>：改顯示在正上方（貼著畫面下緣的東西用，例如佈置托盤 —— 往下會跑出畫面）。
        /// </summary>
        public static void Tip(VisualElement target, Label tip, VisualElement host, string text, bool above = false)
        {
            target.RegisterCallback<PointerEnterEvent>(_ =>
            {
                var r = host.WorldToLocal(target.worldBound);
                tip.text = text;
                tip.style.left = r.center.x;
                tip.style.top = above ? r.yMin - 3 : r.yMax + 3;
                // 往上：整顆再往上推自己的高度（-100%）；往下：交回 uss 的 translate -50% 0
                tip.style.translate = above
                    ? new StyleTranslate(new Translate(Length.Percent(-50f), Length.Percent(-100f)))
                    : new StyleTranslate(StyleKeyword.Null);
                tip.style.display = DisplayStyle.Flex;
                tip.BringToFront();
            });
            target.RegisterCallback<PointerLeaveEvent>(_ => HideTip(tip));
        }

        /// <summary>收起浮動說明（列表重建時要叫：被 Clear 掉的元素不會再送 PointerLeave）。</summary>
        public static void HideTip(Label tip)
        {
            if (tip != null) tip.style.display = DisplayStyle.None;
        }

        // ── 愛心 ─────────────────────────────────────────────

        /// <summary>友誼度：外觀開著用愛心小圖（實心／空心），關著退回 ♥♡ 文字。</summary>
        public static VisualElement Hearts(int on, int max)
        {
            var box = new VisualElement();
            box.AddToClassList("vil-hearts");
            if (!On)
            {
                var l = new Label(new string('♥', on) + new string('♡', Mathf.Max(0, max - on)));
                l.AddToClassList("vil-hearts-text");
                box.Add(l);
                return box;
            }
            for (int i = 0; i < max; i++) box.Add(Ico(i < on ? "heart" : "heart-off"));
            return box;
        }
    }
}
