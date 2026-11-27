using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 調配藥水面板：一本攤開的魔法配方書 —— 一次看一個配方，左右翻頁；書下面一排是所有配方的成品小圖（目錄格），
    /// 點哪格就翻到哪頁。走到鍋爐前按 E 開啟。
    ///
    /// ⚠️ 材料算的是**背包＋倉庫**（PotionRecipes 走 Storage.AvailableOf）——
    ///    倉庫就在同一個房間的木箱裡，只看背包的話回到鍋爐前會什麼都做不了。
    ///
    /// ── 版面（樣式在 Resources/ui/Skin8Book.uss，圖由 tools/gen_ui_book.py 產生）──────
    ///   左頁：魔法陣＋成品大圖 144、名稱、一句說明（Items.DescOf）、金幣售價、頁碼「3 / 13」
    ///   右頁：「材料」小標、材料卡（材料圖 48＋持有/需要，夠＝綠、不夠＝紅；滑鼠移上去浮出名稱）、
    ///         可做幾份（成品小圖＋×N）、熬 1（綠）／熬 N（金）
    ///   書兩側：翻頁箭頭；書下：目錄條（目前這頁＝亮金框往上抬、做得出來＝右上小綠寶石、做不出來＝暗格淡圖但仍可點）
    ///   以前是一張 13 列的清單（每列 [成品][名稱][材料小卡…][售價][熬 1][熬 N]），使用者要的是「翻書」。
    ///
    /// ── 目錄條分頁（2026-11-28，使用者：「下面的道具要有下一頁，怕會無限延伸變很長」）──────
    ///   固定寬度、一頁 <see cref="StripPer"/> 格，兩端各一顆小翻頁鈕 [◀][格×10][▶]；最後一頁不滿就補空位，寬度永遠不變。
    ///   只有一頁時兩顆鈕藏起來但位置照留；到頭的那顆變暗停用（同 Pager 的慣例，翻頁響 `page`）。
    ///   目錄條跟著書走：書翻到別一頁目錄上的配方（箭頭、←／→、A／D、滾輪），目錄條也翻過去；
    ///   點目錄條的鈕只換目錄條的頁、不換攤開的配方；點格子照舊翻到那個配方。
    ///   滾輪：在目錄條上＝翻目錄條（StopPropagation，書不會跟著翻）；在書上＝翻配方。
    ///   格子每次換頁重建（跟 Pager 一樣），浮動說明跟著新格子註冊。
    ///
    /// ── 翻頁 ─────────────────────────────────────────────────
    ///   ←／→、A／D、滑鼠滾輪、兩側箭頭、點目錄格。首尾相接循環。
    ///   動畫全走 USS transition＋schedule（見 Skin8Book.uss 檔頭與 <see cref="StartFlip"/>），不每幀配置。
    ///   翻頁中再按：記住**一個**目標（<see cref="queued"/>），這一頁翻完再翻過去 —— 連按不會排一長串；
    ///   滾輪在翻頁中與翻完 0.25 秒內直接忽略（觸控板一次會送一大串滾輪事件）。
    ///   上次停在哪一頁記在 <see cref="page"/>（只在記憶體），關掉再開回到同一頁；熬下去照舊關面板看鍋爐冒泡，
    ///   熬完再開就是同一頁、數字重算過。
    ///
    /// ⚠️ 這個面板只有 8-bit 翻書版：<see cref="UiSkin.Enabled"/> 關掉時書本身照樣畫（Skin8Book.uss 只看自己的 `bk` class），
    ///    只有按鈕、材料卡底、鍵帽這些沿用 Skin8 的零件會退回舊的純色塊。
    /// </summary>
    public class BrewPanel : MonoBehaviour
    {
        public static BrewPanel Instance { get; private set; }

        public static BrewPanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("BrewUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<BrewPanel>();
        }

        const string BookSheetPath = "ui/Skin8Book";
        /// <summary>根上的 class；Skin8Book.uss 的規則全部以它開頭。</summary>
        const string RootClass = "bk";

        /// <summary>翻起來那段（毫秒）。⚠️ 跟 Skin8Book.uss 的 .bk-leaf--fold 同步。</summary>
        const long FoldMs = 100;
        /// <summary>展開那段（毫秒）。⚠️ 跟 Skin8Book.uss 的 .bk-leaf--open 同步。</summary>
        const long OpenMs = 110;
        /// <summary>滾輪翻頁的最短間隔（秒，真實時間）。</summary>
        const float WheelGap = 0.25f;
        /// <summary>目錄條一頁幾格。⚠️ 跟 Skin8Book.uss 的 .bk-strip-row 寬（60×10＋6×9＝654）與 book-shelf 圖寬同步。</summary>
        const int StripPer = 10;
        /// <summary>目錄條滾輪翻頁的最短間隔（秒，真實時間；同 Pager）。</summary>
        const float StripWheelGap = 0.2f;

        const string FoldClass = "bk-leaf--fold";
        const string FlatClass = "bk-leaf--flat";
        const string FadeClass = "bk-leaf--fade";
        const string OpenClass = "bk-leaf--open";

        UIDocument doc;
        VisualElement root;
        VisualElement panel;
        Label tip;
        BrewCauldron cauldron;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        // ── 書頁上的元素（Build 時建一次，翻頁時只換內容）──
        VisualElement leftLeaf, rightLeaf;
        VisualElement heroIcon, priceBox, matsRow, canIcon;
        Label nameLabel, descLabel, pageLabel, canNum;
        Button brewOne, brewMax;

        // ── 目錄條（分頁）──
        VisualElement stripRow;
        Button stripPrev, stripNext;
        /// <summary>目錄條目前第幾頁（0 起算）。</summary>
        int stripPage;
        /// <summary>目錄條上次「跟著書走」時對的是哪個配方；書翻到別的配方才重新對齊（-1＝開面板時強制對齊）。</summary>
        int stripFor = -1;
        float stripWheelReadyAt;

        /// <summary>目前攤開的配方（Recipes.All 的索引）。關掉再開回到這頁。</summary>
        int page;
        /// <summary>目前這頁最多能熬幾份（「熬 N」按鈕用）。</summary>
        int curMax;

        // ── 翻頁狀態 ──
        bool flipping;
        int flipTarget = -1;
        /// <summary>翻頁中又要求的下一個目標（-1＝沒有）。只記一個。</summary>
        int queued = -1;
        int queuedDir;
        /// <summary>每次開始翻頁／重設就 +1；排程回呼比對它，舊的回呼就算漏網也不會作用（同 UIAnim 的 serial）。</summary>
        int flipSerial;
        IVisualElementScheduledItem flipJob;
        float wheelReadyAt;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[BrewPanel] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null || !anim.IsOpen) return;
            if (Input.GetKeyDown(KeyCode.Escape)) { Close(); return; }
            if (Input.GetKeyDown(KeyCode.LeftArrow) || Input.GetKeyDown(KeyCode.A)) Step(-1);
            else if (Input.GetKeyDown(KeyCode.RightArrow) || Input.GetKeyDown(KeyCode.D)) Step(1);
        }

        public void Open(BrewCauldron c)
        {
            cauldron = c;
            if (!built) Build();
            if (!built) return;
            ResetFlip();                 // 上次關掉時若還在翻頁，先把半張葉子收好
            stripFor = -1;               // 目錄條回到攤開的那個配方所在的頁
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            Sfx.Play("ui-open");                                    // 音效：面板打開
            GameArt.OnReady(Refresh);
        }

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        // ═══════════════════════════════ 建立 ═══════════════════════════════

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[BrewPanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));   // .dim 暗幕
            UiSkin.Apply(root);           // 按鈕、材料卡底、鍵帽、浮動說明沿用 8-bit 外觀
            var book = Resources.Load<StyleSheet>(BookSheetPath);
            if (book != null) root.styleSheets.Add(book);
            else Debug.LogWarning($"[BrewPanel] 找不到 Resources/{BookSheetPath}.uss（新檔要等 Unity 匯入過）");
            root.AddToClassList(RootClass);
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            panel = new VisualElement();
            panel.AddToClassList("bk-panel");
            panel.RegisterCallback<WheelEvent>(OnWheel);
            dim.Add(panel);

            BuildBook(panel);
            BuildShelf(panel);
            BuildFooter(panel);

            tip = UiSkin.MakeTip(panel);   // 材料卡／目錄格的浮動說明（最後加 → 疊在最上面）

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        void BuildBook(VisualElement parent)
        {
            var book = new VisualElement();
            book.AddToClassList("bk-book");
            parent.Add(book);

            // 每一側：底下一張不動的空白頁＋上面一張會翻的葉子
            var leftPage = new VisualElement();
            leftPage.AddToClassList("bk-page");
            leftPage.AddToClassList("bk-page--l");
            book.Add(leftPage);
            leftLeaf = new VisualElement();
            leftLeaf.AddToClassList("bk-leaf");
            leftLeaf.AddToClassList("bk-leaf--l");
            leftPage.Add(leftLeaf);

            var rightPage = new VisualElement();
            rightPage.AddToClassList("bk-page");
            rightPage.AddToClassList("bk-page--r");
            book.Add(rightPage);
            rightLeaf = new VisualElement();
            rightLeaf.AddToClassList("bk-leaf");
            rightLeaf.AddToClassList("bk-leaf--r");
            rightPage.Add(rightLeaf);

            BuildLeftLeaf(leftLeaf);
            BuildRightLeaf(rightLeaf);

            // 書上的零件（後加 → 疊在書頁上面）
            book.Add(Pic("bk-mark"));

            var title = new Label("調配藥水");
            title.AddToClassList("bk-title");
            title.pickingMode = PickingMode.Ignore;
            book.Add(title);

            var close = new Button(Close) { text = "×", focusable = false };
            close.AddToClassList("close");          // 圖與滑過／按下沿用 Skin8 的 .sk .close
            close.AddToClassList("bk-close");
            book.Add(close);

            var prev = new Button(() => Step(-1)) { text = "", focusable = false };
            prev.AddToClassList("bk-arrow");
            prev.AddToClassList("bk-arrow--l");
            book.Add(prev);

            var next = new Button(() => Step(1)) { text = "", focusable = false };
            next.AddToClassList("bk-arrow");
            next.AddToClassList("bk-arrow--r");
            book.Add(next);
        }

        /// <summary>左頁：魔法陣＋成品大圖、名稱、說明、售價、頁碼。</summary>
        void BuildLeftLeaf(VisualElement leaf)
        {
            leaf.Add(Pic("bk-deco", "bk-star", "bk-star--a"));
            leaf.Add(Pic("bk-deco", "bk-star", "bk-star--b"));
            leaf.Add(Pic("bk-deco", "bk-star", "bk-star--c"));

            var hero = Pic("bk-hero");
            leaf.Add(hero);
            heroIcon = Pic("bk-hero-icon");
            hero.Add(heroIcon);

            nameLabel = Text("bk-name");
            leaf.Add(nameLabel);
            descLabel = Text("bk-desc");
            leaf.Add(descLabel);

            priceBox = new VisualElement();
            priceBox.AddToClassList("bk-price");
            priceBox.pickingMode = PickingMode.Ignore;
            leaf.Add(priceBox);

            pageLabel = Text("bk-pageno");
            leaf.Add(pageLabel);
        }

        /// <summary>右頁：「材料」小標、材料卡、可做幾份、熬 1／熬 N。</summary>
        void BuildRightLeaf(VisualElement leaf)
        {
            leaf.Add(Pic("bk-deco", "bk-moon"));
            leaf.Add(Pic("bk-deco", "bk-vine"));

            var head = new VisualElement();
            head.AddToClassList("bk-head");
            head.pickingMode = PickingMode.Ignore;
            head.Add(Pic("bk-star"));
            var headText = new Label("材料");
            headText.AddToClassList("bk-head-text");
            headText.pickingMode = PickingMode.Ignore;
            head.Add(headText);
            head.Add(Pic("bk-star"));
            leaf.Add(head);

            matsRow = new VisualElement();
            matsRow.AddToClassList("bk-mats");
            leaf.Add(matsRow);

            var can = new VisualElement();
            can.AddToClassList("bk-can");
            can.pickingMode = PickingMode.Ignore;
            canIcon = Pic("bk-can-icon");
            can.Add(canIcon);
            canNum = Text("bk-can-num");
            can.Add(canNum);
            leaf.Add(can);

            var btns = new VisualElement();
            btns.AddToClassList("bk-btns");
            leaf.Add(btns);

            brewOne = new Button(() => BrewCurrent(1)) { text = "熬 1", focusable = false };
            brewOne.AddToClassList("btn"); brewOne.AddToClassList("btn-list"); brewOne.AddToClassList("bk-brew");
            btns.Add(brewOne);

            brewMax = new Button(() => BrewCurrent(curMax)) { text = "熬最大", focusable = false };
            brewMax.AddToClassList("btn"); brewMax.AddToClassList("btn-buy"); brewMax.AddToClassList("bk-brew");
            btns.Add(brewMax);
        }

        /// <summary>
        /// 書下面的目錄條：[◀][一頁 StripPer 格][▶]，固定寬度（格子內容由 <see cref="RenderStrip"/> 每次換頁重建）。
        /// 點格子直接翻到那個配方；點兩端的鈕只換目錄條的頁。
        /// </summary>
        void BuildShelf(VisualElement parent)
        {
            var shelf = new VisualElement();
            shelf.AddToClassList("bk-shelf");
            shelf.RegisterCallback<WheelEvent>(OnStripWheel);    // 目錄條上的滾輪只翻目錄條（不往上傳給書）
            parent.Add(shelf);

            stripPrev = new Button(() => StepStrip(-1)) { text = "", focusable = false };
            stripPrev.AddToClassList("bk-sarrow");
            stripPrev.AddToClassList("bk-sarrow--l");
            shelf.Add(stripPrev);

            stripRow = new VisualElement();
            stripRow.AddToClassList("bk-strip-row");
            shelf.Add(stripRow);

            stripNext = new Button(() => StepStrip(1)) { text = "", focusable = false };
            stripNext.AddToClassList("bk-sarrow");
            stripNext.AddToClassList("bk-sarrow--r");
            shelf.Add(stripNext);
        }

        /// <summary>底列：[Esc] 關閉　[←][→] 翻頁（置中，暗幕上用淺色字）。</summary>
        void BuildFooter(VisualElement parent)
        {
            var foot = new VisualElement();
            foot.AddToClassList("bk-foot");
            foot.pickingMode = PickingMode.Ignore;
            parent.Add(foot);
            foot.Add(UiSkin.KeyCap("Esc"));
            foot.Add(Text("bk-foot-text", "關閉"));
            foot.Add(Pic("bk-foot-gap"));
            foot.Add(UiSkin.KeyCap("←"));
            foot.Add(UiSkin.KeyCap("→"));
            foot.Add(Text("bk-foot-text", "翻頁"));
        }

        /// <summary>不收滑鼠的純圖元素（背景圖由 class 給）。</summary>
        static VisualElement Pic(params string[] classes)
        {
            var el = new VisualElement();
            foreach (var c in classes) el.AddToClassList(c);
            el.pickingMode = PickingMode.Ignore;
            return el;
        }

        static Label Text(string cls, string text = "")
        {
            var l = new Label(text);
            l.AddToClassList(cls);
            l.pickingMode = PickingMode.Ignore;
            return l;
        }

        // ═══════════════════════════════ 填內容 ═══════════════════════════════

        void Refresh()
        {
            if (!built) return;
            Fill();                       // 目錄條的成品圖與浮動說明在 RenderStrip（圖要等 GameArt 載好，所以不放 Build）
        }

        /// <summary>把目前這頁（<see cref="page"/>）的配方填進兩頁，並更新目錄格的狀態。</summary>
        void Fill()
        {
            var all = Recipes.All;
            if (all.Length == 0) return;
            page = Wrap(page);
            var r = all[page];
            int max = PotionRecipes.MaxCraftable(r);
            curMax = max;
            UiSkin.HideTip(tip);          // 材料卡要重建，被 Clear 掉的卡不會再送 PointerLeave

            // 左頁
            var sp = GameArt.Item(r.Name);
            var bg = sp != null ? new StyleBackground(sp) : new StyleBackground(StyleKeyword.Null);
            heroIcon.style.backgroundImage = bg;
            nameLabel.text = r.Name;
            descLabel.text = Items.DescOf(r.Name);
            priceBox.Clear();
            priceBox.Add(UiSkin.Money(r.SellPrice, "bk-price-num"));
            pageLabel.text = $"{page + 1} / {all.Length}";

            // 右頁：材料卡（中間一顆燙金「＋」）。材料欄固定寬、超出隱藏；4 種材料換窄卡、5 種以上再窄一號（小圖 36）
            matsRow.Clear();
            int nMats = r.Inputs.Count;
            matsRow.EnableInClassList("bk-mats--4", nMats == 4);
            matsRow.EnableInClassList("bk-mats--5", nMats >= 5);
            bool first = true;
            foreach (var kv in r.Inputs)
            {
                if (!first) matsRow.Add(Pic("bk-plus"));
                first = false;
                matsRow.Add(MaterialCard(kv.Key, kv.Value));
            }

            canIcon.style.backgroundImage = bg;
            canNum.text = $"×{max}";
            canNum.EnableInClassList("bk-can-num--zero", max < 1);

            brewOne.SetEnabled(max >= 1);
            brewMax.text = max > 0 ? $"熬 {max}" : "熬最大";
            brewMax.SetEnabled(max >= 1);

            // 目錄條：書翻到別的配方 → 目錄條翻到那個配方所在的頁（使用者自己翻目錄條時 page 沒變，不會被拉回來）
            if (page != stripFor)
            {
                stripPage = page / StripPer;
                stripFor = page;
            }
            RenderStrip();
        }

        // ═══════════════════════════════ 目錄條 ═══════════════════════════════

        int StripPages => Mathf.Max(1, (Recipes.All.Length + StripPer - 1) / StripPer);

        /// <summary>
        /// 重建目錄條這一頁的 StripPer 格：配方格（目前這頁＝--sel 亮金框抬起、做得出來＝--can 小綠寶石、做不出來＝--off 暗格淡圖仍可點）、
        /// 不滿一頁的補空位（--empty，不收滑鼠），寬度永遠不變。兩端的鈕：到頭停用、只有一頁時藏起來但位置照留。
        /// </summary>
        void RenderStrip()
        {
            if (stripRow == null) return;
            var all = Recipes.All;
            int pages = StripPages;
            stripPage = Mathf.Clamp(stripPage, 0, pages - 1);
            UiSkin.HideTip(tip);          // 被 Clear 掉的格子不會再送 PointerLeave
            stripRow.Clear();
            for (int i = 0; i < StripPer; i++)
            {
                int idx = stripPage * StripPer + i;
                VisualElement slot;
                if (idx < all.Length)
                {
                    bool can = PotionRecipes.MaxCraftable(all[idx]) >= 1;
                    slot = new VisualElement();
                    slot.AddToClassList("bk-slot");
                    slot.EnableInClassList("bk-slot--sel", idx == page);
                    slot.EnableInClassList("bk-slot--can", can);
                    slot.EnableInClassList("bk-slot--off", !can);
                    slot.RegisterCallback<ClickEvent>(_ => GoTo(idx));
                    var ic = Pic("bk-slot-icon");
                    var sp = GameArt.Item(all[idx].Name);
                    if (sp != null) ic.style.backgroundImage = new StyleBackground(sp);
                    slot.Add(ic);
                    slot.Add(Pic("bk-slot-dot"));
                    UiSkin.Tip(slot, tip, panel, all[idx].Name);
                }
                else
                {
                    slot = Pic("bk-slot", "bk-slot--empty");
                }
                if (i == StripPer - 1) slot.AddToClassList("bk-slot--end");
                stripRow.Add(slot);
            }
            stripPrev.SetEnabled(stripPage > 0);
            stripNext.SetEnabled(stripPage < pages - 1);
            var vis = pages > 1 ? Visibility.Visible : Visibility.Hidden;
            stripPrev.style.visibility = vis;
            stripNext.style.visibility = vis;
        }

        /// <summary>目錄條往前／往後一頁（不換攤開的配方）。到頭不動、不出聲。</summary>
        void StepStrip(int dir)
        {
            int target = stripPage + (dir < 0 ? -1 : 1);
            if (target < 0 || target >= StripPages) return;
            stripPage = target;
            Sfx.Play("page");                                       // 音效：翻頁的紙張「唰」（同 Pager）
            RenderStrip();
        }

        void OnStripWheel(WheelEvent e)
        {
            e.StopPropagation();          // 不讓書（panel 上的 OnWheel）跟著翻
            if (anim == null || !anim.IsOpen) return;
            if (StripPages < 2 || Mathf.Abs(e.delta.y) < 0.01f || Time.unscaledTime < stripWheelReadyAt) return;
            stripWheelReadyAt = Time.unscaledTime + StripWheelGap;
            StepStrip(e.delta.y > 0 ? 1 : -1);
        }

        /// <summary>
        /// 一張材料卡：[材料圖 48]／[持有/需要]，數量不足的整張換成 bk-mat--short（紅字淡紅底）。
        /// 名稱不寫在卡上（圖就是名字），滑鼠移上去才浮出「藍莓　有 3／要 2」。
        /// </summary>
        VisualElement MaterialCard(string mat, int need)
        {
            int have = Storage.AvailableOf(mat);
            var card = new VisualElement();
            card.AddToClassList("bk-mat");
            if (have < need) card.AddToClassList("bk-mat--short");

            var sp = GameArt.Item(mat);
            var ic = Pic("bk-mat-icon");
            if (sp != null) ic.style.backgroundImage = new StyleBackground(sp);
            card.Add(ic);

            // 沒有圖（理論上不會）就把名字寫出來，不要只剩一個數字
            var num = Text("bk-mat-num", sp != null ? $"{have}/{need}" : $"{mat} {have}/{need}");
            if (sp == null) num.AddToClassList("bk-mat-num--name");
            card.Add(num);

            UiSkin.Tip(card, tip, panel, $"{mat}　有 {have}／要 {need}");
            return card;
        }

        // ═══════════════════════════════ 翻頁 ═══════════════════════════════

        static int Wrap(int i)
        {
            int n = Recipes.All.Length;
            return n == 0 ? 0 : ((i % n) + n) % n;
        }

        /// <summary>往前／往後翻一頁（首尾相接）。翻頁中按的話，以「正在翻去的那頁」為基準，只多排一頁。</summary>
        void Step(int dir)
        {
            if (Recipes.All.Length < 2) return;
            int from = flipping ? flipTarget : page;
            RequestFlip(Wrap(from + dir), dir);
        }

        /// <summary>點目錄格：直接翻到那一頁（往後的格子就往後翻，往前就往前翻）。</summary>
        void GoTo(int target)
        {
            if (anim == null || !anim.IsOpen) return;
            int from = flipping ? flipTarget : page;
            if (target == from) { queued = -1; return; }
            RequestFlip(target, target > from ? 1 : -1);
        }

        void RequestFlip(int target, int dir)
        {
            if (flipping) { queued = target; queuedDir = dir; return; }
            if (target == page) return;
            StartFlip(target, dir);
        }

        void OnWheel(WheelEvent e)
        {
            if (anim == null || !anim.IsOpen) return;
            e.StopPropagation();
            if (flipping || Time.unscaledTime < wheelReadyAt || Mathf.Abs(e.delta.y) < 0.01f) return;
            wheelReadyAt = Time.unscaledTime + WheelGap;
            Step(e.delta.y > 0 ? 1 : -1);
        }

        /// <summary>
        /// 翻頁動畫（樣式在 Skin8Book.uss）。往後翻（dir &gt; 0）：
        ///   1. 右頁葉子以書脊為軸壓扁（--fold，FoldMs）。
        ///   2. 中點：換成新配方；右葉瞬間回正但透明（--fade）、左葉瞬間壓扁在書脊（--flat）。
        ///   3. 隔兩個排程 tick（讓瞬間狀態先被樣式解析一次，見 UIAnim 類別註解第 2 點），兩張一起換 --open：
        ///      左葉從書脊展開、右葉淡入（OpenMs）。
        ///   4. 收尾：拿掉所有 class；翻頁中有人又要求別頁（queued）就接著翻過去。
        /// 往前翻左右對調。全部走 schedule（真實時間毫秒），不碰 MonoBehaviour 的 Update。
        /// </summary>
        void StartFlip(int target, int dir)
        {
            flipping = true;
            flipTarget = target;
            int my = ++flipSerial;
            UiSkin.HideTip(tip);
            Sfx.Play("page");                                       // 音效：翻頁的紙張「唰」

            var fold = dir > 0 ? rightLeaf : leftLeaf;
            var other = dir > 0 ? leftLeaf : rightLeaf;
            ClearLeaf(leftLeaf);
            ClearLeaf(rightLeaf);
            fold.AddToClassList(FoldClass);

            flipJob = root.schedule.Execute(() =>
            {
                if (my != flipSerial) return;
                page = target;
                Fill();
                fold.RemoveFromClassList(FoldClass);
                fold.AddToClassList(FadeClass);
                other.AddToClassList(FlatClass);
                flipJob = root.schedule.Execute(() =>
                {
                    if (my != flipSerial) return;
                    flipJob = root.schedule.Execute(() =>
                    {
                        if (my != flipSerial) return;
                        fold.RemoveFromClassList(FadeClass);
                        other.RemoveFromClassList(FlatClass);
                        fold.AddToClassList(OpenClass);
                        other.AddToClassList(OpenClass);
                        flipJob = root.schedule.Execute(() =>
                        {
                            if (my != flipSerial) return;
                            EndFlip();
                        }).StartingIn(OpenMs + 30);
                    });
                });
            }).StartingIn(FoldMs);
        }

        void EndFlip()
        {
            flipping = false;
            flipJob = null;
            ClearLeaf(leftLeaf);
            ClearLeaf(rightLeaf);
            if (queued < 0) return;
            int t = queued, d = queuedDir;
            queued = -1;
            if (t != page && anim != null && anim.IsOpen) StartFlip(t, d);
        }

        /// <summary>作廢翻到一半的動畫，兩張葉子回到平放（開面板時呼叫）。</summary>
        void ResetFlip()
        {
            flipSerial++;
            flipJob?.Pause();
            flipJob = null;
            flipping = false;
            queued = -1;
            ClearLeaf(leftLeaf);
            ClearLeaf(rightLeaf);
        }

        static void ClearLeaf(VisualElement leaf)
        {
            if (leaf == null) return;
            leaf.RemoveFromClassList(FoldClass);
            leaf.RemoveFromClassList(FlatClass);
            leaf.RemoveFromClassList(FadeClass);
            leaf.RemoveFromClassList(OpenClass);
        }

        // ═══════════════════════════════ 熬 ═══════════════════════════════

        void BrewCurrent(int qty)
        {
            if (flipping) return;         // 翻頁中畫面上的配方跟 page 可能對不上，不收
            var all = Recipes.All;
            if (all.Length == 0) return;
            Brew(all[Wrap(page)], qty);
        }

        void Brew(Recipe r, int qty)
        {
            if (cauldron == null || qty <= 0) return;
            cauldron.StartBrew(r, qty);
            Close();          // 關掉面板才看得到鍋爐在冒泡
        }
    }
}
