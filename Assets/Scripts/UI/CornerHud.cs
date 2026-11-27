using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;

namespace WitchShop.UI
{
    /// <summary>
    /// 畫面上方的工具列（左上角往右排成一條）：
    ///
    ///   [金幣] ┃ [名聲 Lv／稱號＋進度條] ┃ [開店／關店鈕][R 佈置提示（店裡＝佈置店面、8-bit 後花園＝搬花圃）] ┃ [設定 (O)]
    ///
    /// 名聲會影響來客速度與人數，所以放在玩家隨時看得到的地方 ——
    /// 「好好經營 → 店更熱鬧」這條回饋要看得見才有意義。
    ///
    /// 由 PlayerController 每個場景喚起（跟下排背包 HUD、時鐘同一批），
    /// 走到哪都看得到，不用逐場景擺 UI。
    ///
    /// ── 開店／關店鈕（使用者實機回饋：「開關店要做在工具列上啦XD（上方）」）──
    ///   以前是店門口的招牌、走近按 E 切換；現在入口改到這裡，門口招牌（ShopSignPost）只負責顯示。
    ///   **每個場景都能按**：在外面採集時也能把店關掉／打開（離店營業 AwayShop 看的就是 ShopSign.Serving）。
    ///   · 圖示為主：亮的招牌＝開店、暗的招牌＝關店，旁邊一顆 P 鍵帽＝熱鍵。
    ///   · 點一下或按 P → ShopSign.Toggle()（存檔、風鈴聲都在 ShopSign.SetOpen）。
    ///   · 狀態訂閱 ShopSign.Changed，不每幀查；切換時按鈕彈一下（UIAnim.Bump）。
    ///   · 開著面板（UIState.ModalOpen）或佈置模式中不能切換；佈置中按鈕顯示成停用。
    ///   · 連按有冷卻（<see cref="ToggleCooldown"/>）：門口招牌的翻面動畫跟風鈴聲才不會疊成一團。
    ///   · 開店中按 R 被擋下來時，ShopRoomEditor 會叫 <see cref="NudgeShop"/>：按鈕抖一下＋閃紅框，指給玩家看。
    ///
    /// ── 樣式 ───────────────────────────────────────────────
    /// 像素外觀開著（<see cref="UiSkin.On"/>）時跟其他面板一樣套 skin8 的九宮格（Skin8.uss 的「上方工具列」那段）：
    /// 底座＝下排背包列同一塊深木 hud-bar；開店＝金鈕、關店＝紫鈕、佈置中＝灰鈕；R 提示＝金／深木膠囊；
    /// 金幣用金幣圖＋數字、名聲用星星圖＋「Lv＋稱號｜點數」＋進度條、設定用 [齒輪][O]。
    /// 外觀關著時退回 HudExtraStyle.uss 的 .hud-*（純 background-color／border 的雙色邊木條，當初九宮格還壞著時做的）。
    /// ⚠️ 名聲進度條的 class 是 hud-rep-bar —— hud-bar 是下排背包列底座的 class，同名會被 Skin8 蓋成一整塊木頭。
    /// ⚠️ 兩種外觀只差在 Build 建了哪些子元素與圖示大小；行為（點擊範圍、熱鍵、冷卻、抖動、R 提示的 visibility）完全共用。
    ///
    /// ── 點擊 ───────────────────────────────────────────────
    /// 整條工具列的空白處不吃滑鼠（PickingMode.Ignore），只有按鈕吃。
    /// ⚠️ 點地面走路（PlayerController）讀的是 Input.GetMouseButtonDown，完全不看 UI ——
    ///    所以它會先問 <see cref="BlocksWorldClick"/>：落在**整條工具列**上就不走（點到金幣數字旁邊也不該往左上角走）。
    /// ⚠️ 按鈕一律 focusable = false：UI Toolkit 的按鈕被點過會拿到焦點，之後按 Space／Enter 會「再點一次」——
    ///    Space 是施法鍵，不關掉的話施法會順便把店關掉。
    ///
    /// ⚠️ 叫 CornerHud 而不是 Hud —— UnityEngine 沒有同名的東西，但專案裡已經有
    ///    InventoryHud / ClockHud，統一用 XxxHud 的命名比較好認。（現在是一整條工具列，名字沿用。）
    /// </summary>
    public class CornerHud : MonoBehaviour
    {
        public static CornerHud Instance { get; private set; }

        public static CornerHud Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("CornerHud");
            DontDestroyOnLoad(go);
            return go.AddComponent<CornerHud>();
        }

        /// <summary>開店／關店的熱鍵。E/R/F/T/O/B/Q/I/J/M/Tab/Space/F3/Esc 都被用掉了。</summary>
        public const KeyCode ShopKey = KeyCode.P;

        /// <summary>兩次切換之間至少隔多久（秒）。比門口招牌的翻面（ShopSignPost.FlipTime 0.32）長一點。</summary>
        const float ToggleCooldown = 0.35f;

        // 圖示高度：像素外觀時一律 24（＝圖的邏輯格 1:1，放進 36 高的九宮格鈕剛好）；舊外觀照原本的大小
        static float ShopIconH => UiSkin.On ? 24f : 32f;   // 招牌圖（24 格）
        const float ShopKeyH = 24f;                        // P 鍵帽（24 格 → 24px，剛好一倍）
        static float EditIconH => UiSkin.On ? 24f : 28f;

        /// <summary>NudgeShop 抖動的角度序列（度），每 <see cref="ShakeStepMs"/> 換一格。</summary>
        static readonly float[] ShakeDeg = { -9f, 9f, -7f, 7f, -4f, 4f, 0f };
        const long ShakeStepMs = 45;

        UIDocument doc;
        /// <summary>整條工具列的外框（BlocksWorldClick 量的就是它）。</summary>
        VisualElement bar;
        Label goldLabel, repLabel;
        /// <summary>像素外觀時名聲點數另外一個小字（「86/120」）；舊外觀時是 null（點數寫在 repLabel 裡）。</summary>
        Label repNum;
        VisualElement barFill;
        Button settingsBtn;

        /// <summary>開店／關店鈕與它裡面的招牌圖。</summary>
        Button shopBtn;
        VisualElement shopIcon;
        /// <summary>上一次畫的是不是開店；null ＝ 還沒畫過（第一次畫不彈）。</summary>
        bool? shopOpenShown;
        /// <summary>按鈕現在是不是停用（佈置模式中）。</summary>
        bool shopLocked;
        float lastToggleAt = -10f;
        IVisualElementScheduledItem shakeItem;

        /// <summary>
        /// 店裡的佈置提示：[R 鍵帽(+鎖)][木槌]，緊貼在開關店鈕右邊。
        /// 開店中 R 與木槌變灰、R 上掛一把鎖 —— 一眼看懂「關店才能按 R」。
        /// 只在店裡佔位（display）；佈置中、開著面板時只隱藏不收位（visibility），後面的設定鈕才不會跳來跳去。
        /// </summary>
        VisualElement editHint, editLock;
        /// <summary>editInShop：R 提示有沒有佔位（店裡或 8-bit 後花園）；editIsShop：是店裡（開店中要上鎖）還是後花園（不用關店）。</summary>
        bool editInShop, editIsShop, editVisible = true;
        /// <summary>上一次畫的是不是開店（R 上鎖）；null ＝ 還沒畫過。</summary>
        bool? editOpenShown;

        int lastGold = int.MinValue, lastPoints = int.MinValue;
        bool built;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 5;          // 同時鐘：在面板之下、遊戲畫面之上
            if (doc.panelSettings == null)
            {
                Debug.LogError("[CornerHud] 找不到 Resources/ui/UIPanelSettings");
                return;
            }
            Build();
        }

        void OnDestroy()
        {
            ShopSign.Changed -= OnSignChanged;
            if (Instance == this) Instance = null;
        }

        /// <summary>
        /// 開店中按了 R（ShopRoomEditor 擋下來時叫）：HUD 的佈置提示彈一下、閃紅框，
        /// 讓玩家看到「R 現在是鎖著的」。
        /// </summary>
        public void NudgeEdit()
        {
            if (editHint == null || !editInShop || !editVisible) return;
            UIAnim.Bump(editHint, "hud-edit--nudge");
        }

        /// <summary>
        /// 開關店鈕抖一下＋閃紅框（開店中按 R 被擋下來時，ShopRoomEditor 叫）——
        /// 「要佈置，先點這裡關店」。連續叫會從頭再抖，不會疊。
        /// </summary>
        public void NudgeShop()
        {
            if (shopBtn == null) return;
            shakeItem?.Pause();
            shopBtn.AddToClassList("hud-shop--nudge");
            int step = 0;
            shakeItem = shopBtn.schedule.Execute(() =>
            {
                if (step >= ShakeDeg.Length)
                {
                    shopBtn.style.rotate = StyleKeyword.Null;
                    shopBtn.RemoveFromClassList("hud-shop--nudge");
                    shakeItem?.Pause();
                    return;
                }
                shopBtn.style.rotate = new Rotate(new Angle(ShakeDeg[step], AngleUnit.Degree));
                step++;
            }).Every(ShakeStepMs);
        }

        /// <summary>
        /// 這一下滑鼠點擊是不是落在工具列上 —— 是的話 PlayerController 就不把它當成「點地面走過去」。
        /// <paramref name="screenPos"/> 用 <c>Input.mousePosition</c>（左下角原點）。
        ///
        /// 為什麼要這支：點地走路是讀 <c>Input.GetMouseButtonDown</c>，完全不看 UI；別的 HUD 全是
        /// PickingMode.Ignore 所以沒事。按鈕的 click 要等放開才觸發，不擋的話按下去那一下人就已經往左上角走了。
        /// 量的是**整條工具列**在畫面上的實際範圍（所有按鈕都在裡面，之後再加按鈕也不用改這裡），不靠事件順序。
        /// </summary>
        public static bool BlocksWorldClick(Vector2 screenPos)
        {
            var el = Instance != null ? Instance.bar : null;
            if (el == null || el.panel == null) return false;
            if (el.resolvedStyle.display == DisplayStyle.None) return false;
            // 面板座標的 y 是往下的，Input.mousePosition 是往上的 → 先翻過來
            var p = RuntimePanelUtils.ScreenToPanel(el.panel, new Vector2(screenPos.x, Screen.height - screenPos.y));
            return el.worldBound.Contains(p);
        }

        // ──────────── 建 UI ────────────

        void Build()
        {
            var root = doc.rootVisualElement;
            if (root == null) return;
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/HudExtraStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關 UiSkin.Enabled）：跟下排背包列同一塊木頭底座
            bool skin = UiSkin.On;
            root.pickingMode = PickingMode.Ignore;
            CjkFont.Apply(root);

            // 外框（深色粗邊）＋內框（左上亮、右下暗的雙色邊）＝ 8-bit 的凸起木條
            bar = new VisualElement { pickingMode = PickingMode.Ignore };
            bar.AddToClassList("hud-corner");
            root.Add(bar);
            var row = new VisualElement { pickingMode = PickingMode.Ignore };
            row.AddToClassList("hud-tb");
            bar.Add(row);

            // ① 金幣
            var goldSeg = Seg(row, "hud-seg--gold");
            if (skin) goldSeg.Add(UiSkin.Coin());          // 金幣圖（數字後面就不帶「金」字，見 UiSkin.MoneyText）
            goldLabel = new Label { pickingMode = PickingMode.Ignore };
            goldLabel.AddToClassList("hud-gold");
            goldSeg.Add(goldLabel);
            Sep(row);

            // ② 名聲（上：Lv／稱號，下：進度條）
            //    像素外觀：[星星][上：Lv＋稱號｜點數　下：進度條]；舊外觀：[上：一整句　下：進度條]
            var repSeg = Seg(row, "hud-seg--rep");
            var repBox = repSeg;
            if (skin)
            {
                repSeg.Add(UiSkin.Ico("star"));
                repBox = new VisualElement { pickingMode = PickingMode.Ignore };
                repBox.AddToClassList("sk-hud-rep-box");
                repSeg.Add(repBox);
            }
            var repTop = repBox;
            if (skin)
            {
                repTop = new VisualElement { pickingMode = PickingMode.Ignore };
                repTop.AddToClassList("sk-hud-rep-top");
                repBox.Add(repTop);
            }
            repLabel = new Label { pickingMode = PickingMode.Ignore };
            repLabel.AddToClassList("hud-rep");
            repTop.Add(repLabel);
            if (skin)
            {
                repNum = new Label { pickingMode = PickingMode.Ignore };
                repNum.AddToClassList("sk-hud-rep-num");
                repTop.Add(repNum);
            }
            var repBar = new VisualElement { pickingMode = PickingMode.Ignore };
            repBar.AddToClassList("hud-rep-bar");
            repBox.Add(repBar);
            barFill = new VisualElement { pickingMode = PickingMode.Ignore };
            barFill.AddToClassList("hud-bar-fill");
            repBar.Add(barFill);
            Sep(row);

            // ③ 開店／關店鈕＋（店裡才有的）R 佈置提示
            var shopSeg = Seg(row, "hud-seg--shop");
            shopBtn = new Button(TryToggleShop) { focusable = false };
            shopBtn.AddToClassList("hud-btn");
            shopBtn.AddToClassList("hud-shop");
            shopBtn.pickingMode = PickingMode.Position;
            shopIcon = UiIcons.Element("shop_open", ShopIconH, "hud-shop-icon");
            shopBtn.Add(shopIcon);
            shopBtn.Add(UiIcons.Element("key_p", ShopKeyH, "hud-shop-key"));
            shopSeg.Add(shopBtn);

            // 佈置提示：玩家回饋不知道店可以佈置（R 只寫在佈置模式自己的托盤上，沒進去過就永遠看不到）。
            // 之後又回饋「字太多」「關店才可以擺放貨架」→ 純圖示 [R 鍵帽(+鎖)][木槌]。
            // 招牌狀態就看旁邊那顆開關店鈕，這裡不再放一張招牌圖。只是提示、不吃滑鼠（按 R 才是入口）。
            editHint = new VisualElement { pickingMode = PickingMode.Ignore };
            editHint.AddToClassList("hud-edit");
            var keyBox = new VisualElement { pickingMode = PickingMode.Ignore };
            keyBox.AddToClassList("hud-edit-keybox");
            var editKey = UiIcons.Element("key_r", EditIconH, "hud-edit-icon");
            editKey.AddToClassList("hud-edit-dim");
            keyBox.Add(editKey);
            editLock = UiIcons.Element("lock", 18f, "hud-edit-lock");      // 疊在鍵帽右下角
            keyBox.Add(editLock);
            editHint.Add(keyBox);
            var editTool = UiIcons.Element("act_edit", EditIconH, "hud-edit-icon");
            editTool.AddToClassList("hud-edit-dim");
            editHint.Add(editTool);
            editHint.style.display = DisplayStyle.None;
            shopSeg.Add(editHint);
            Sep(row);

            // ④ 設定入口（開 SettingsPanel）
            var setSeg = Seg(row, "hud-seg--set");
            settingsBtn = new Button(() =>
            {
                if (UIState.ModalOpen) return;      // 對話框這類不蓋暗幕的視窗開著時不疊開設定
                SettingsPanel.Ensure().Open();
            }) { text = "設定 (O)", focusable = false };
            settingsBtn.AddToClassList("hud-btn");
            settingsBtn.AddToClassList("hud-settings");
            if (skin)
            {
                // 像素外觀：[齒輪][O 鍵帽]，不寫字（文字留給舊外觀）
                settingsBtn.text = "";
                settingsBtn.AddToClassList("sk-hud-set");
                settingsBtn.Add(UiSkin.Ico("gear"));
                settingsBtn.Add(UiSkin.KeyCap("O"));
            }
            settingsBtn.pickingMode = PickingMode.Position;
            setSeg.Add(settingsBtn);

            ShopSign.Changed += OnSignChanged;
            RefreshShop();

            built = true;
            Refresh();
        }

        /// <summary>工具列的一格（橫排、垂直置中、不吃滑鼠）。</summary>
        static VisualElement Seg(VisualElement row, string cls)
        {
            var s = new VisualElement { pickingMode = PickingMode.Ignore };
            s.AddToClassList("hud-seg");
            s.AddToClassList(cls);
            row.Add(s);
            return s;
        }

        /// <summary>格與格之間的分隔線（暗一條＋亮一條＝刻進木頭的凹槽）。</summary>
        static void Sep(VisualElement row)
        {
            var s = new VisualElement { pickingMode = PickingMode.Ignore };
            s.AddToClassList("hud-sep");
            row.Add(s);
        }

        // ──────────── 每幀 ────────────

        static bool EditorBusy() => ShopRoomEditor.Instance != null && ShopRoomEditor.Instance.Editing;

        void Update()
        {
            if (!built) return;

            // 熱鍵 P：跟點按鈕走同一條路（同樣的擋法）
            if (Input.GetKeyDown(ShopKey)) TryToggleShop();

            // 佈置模式中開關店鈕停用（只在狀態變的時候改，每幀設會讓 UI Toolkit 一直重排）
            bool locked = EditorBusy();
            if (locked != shopLocked)
            {
                shopLocked = locked;
                shopBtn.SetEnabled(!locked);
            }

            // 店裡（ShopRoomEditor 只在 shop 場景存在）與 8-bit 後花園（GardenArrange：R 搬花圃）才佔位；
            // 沒在佈置、沒開面板才看得到。後花園的 R 不用關店 → 不上鎖。
            // 家裡（HomeArrange：R 擺家具）也一樣，不上鎖（家裡隨時能佈置）。
            var ed = ShopRoomEditor.Instance;
            var ga = GardenArrange.Instance;
            var ha = HomeArrange.Instance;
            bool inShop = ed != null || ga != null || ha != null;
            bool busy = (ed != null && ed.Editing) || (ga != null && ga.Editing) || HomeArrange.Busy;
            bool visible = !inShop || (!busy && !UIState.ModalOpen);
            if (inShop != editInShop || (ed != null) != editIsShop)
            {
                editInShop = inShop;
                editIsShop = ed != null;
                editHint.style.display = inShop ? DisplayStyle.Flex : DisplayStyle.None;
                RefreshEditLock();
            }
            if (visible != editVisible)
            {
                editVisible = visible;
                editHint.style.visibility = visible ? Visibility.Visible : Visibility.Hidden;
            }

            // 數字沒變就不動 UI（每幀重設文字會讓 UI Toolkit 一直重排）
            if (Wallet.Gold != lastGold || Reputation.Points != lastPoints) Refresh();
        }

        // ──────────── 開店／關店 ────────────

        /// <summary>點按鈕或按 P：擋掉不該切換的時機，其餘交給 ShopSign.Toggle（存檔＋風鈴聲）。</summary>
        void TryToggleShop()
        {
            if (UIState.ModalOpen) return;                  // 開著面板／對話框時不切
            if (EditorBusy())                               // 佈置中：按鈕是停用的，這裡只會是按了 P
            {
                Sfx.Play("deny");
                return;
            }
            if (Time.unscaledTime - lastToggleAt < ToggleCooldown) return;
            lastToggleAt = Time.unscaledTime;
            ShopSign.Toggle();                              // 換圖與動畫由 OnSignChanged 接
        }

        void OnSignChanged() => RefreshShop();

        /// <summary>招牌變了（或第一次建）→ 換按鈕的招牌圖與底色、R 上鎖／解鎖。值沒變就不動 UI。</summary>
        void RefreshShop()
        {
            if (shopBtn == null) return;
            bool open = ShopSign.IsOpen;
            if (shopOpenShown != open)
            {
                bool first = shopOpenShown == null;
                shopOpenShown = open;
                UiIcons.Set(shopIcon, open ? "shop_open" : "shop_closed", ShopIconH);
                shopBtn.EnableInClassList("hud-shop--open", open);
                shopBtn.EnableInClassList("hud-shop--closed", !open);
                if (!first) UIAnim.Bump(shopBtn);           // 切換時彈一下（第一次畫不彈）
            }

            RefreshEditLock();
        }

        /// <summary>R 提示上鎖：只有店裡、而且開店中（後花園搬花圃不用關店）。值沒變就不動 UI。</summary>
        void RefreshEditLock()
        {
            if (editHint == null) return;
            bool locked = ShopSign.IsOpen && editIsShop;
            if (editOpenShown != locked)
            {
                editOpenShown = locked;
                editHint.EnableInClassList("hud-edit--locked", locked);
                editLock.style.display = locked ? DisplayStyle.Flex : DisplayStyle.None;
            }
        }

        // ──────────── 金幣／名聲 ────────────

        void Refresh()
        {
            // 金額變了 → 數字跳一下，多了閃綠、少了閃紅。
            // lastGold 還是 MinValue ＝ 第一次畫（開場、讀檔後），只顯示不跳。
            if (lastGold != int.MinValue && Wallet.Gold != lastGold)
                UIAnim.Bump(goldLabel, Wallet.Gold > lastGold ? "hud-gold--up" : "hud-gold--down");

            lastGold = Wallet.Gold;
            lastPoints = Reputation.Points;

            goldLabel.text = UiSkin.MoneyText(lastGold);       // 像素外觀：只有數字（前面有金幣圖）；舊外觀：「1280 金」
            if (repNum != null)
            {
                // 像素外觀：星星圖已經說了「名聲」，這裡只留等級與稱號，點數另外一個小字
                repLabel.text = $"Lv.{Reputation.Level} {Reputation.Title}";
                repNum.text = Reputation.IsMax ? "滿" : $"{lastPoints}/{Reputation.NextNeed}";
            }
            else
            {
                repLabel.text = Reputation.IsMax
                    ? $"名聲 Lv.{Reputation.Level} {Reputation.Title}（滿）"
                    : $"名聲 Lv.{Reputation.Level} {Reputation.Title}　{lastPoints}/{Reputation.NextNeed}";
            }

            barFill.style.width = Length.Percent(Reputation.Progress * 100f);
        }
    }
}
