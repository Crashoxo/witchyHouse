using UnityEngine;
using UnityEngine.UIElements;
using WitchShop.Core;
using WitchShop.Data;

namespace WitchShop.UI
{
    /// <summary>
    /// 衣櫃面板：左欄是造型清單、右欄是大立繪預覽。走到藥水室左邊那座雕花木櫃前按 E 開啟。
    ///
    /// 操作：**點左欄只是預覽**（換右邊的圖與文字），按「換上」才真的 <see cref="Outfits.Set"/>。
    /// 打開時預設選取＝身上那套。
    ///
    /// 造型立繪在 Resources/portraits/outfit8-*.png（196×264 的像素畫，載入在 GameArt 的 brew 組裡，
    /// 因為只有這個房間的衣櫃會用到）。預覽框**照原尺寸**擺，不縮放。
    ///
    /// 版面（面板寬 640，border-box：邊框 4×2、padding 22×2 → 內容寬 588）：
    ///   左欄 200 ＋ 間距 16 ＋ 右欄 372。
    ///   高度：邊框＋padding 44 ＋ 標題列 50 ＋ 右欄（立繪框 284 ＋ 名稱 38 ＋ 說明 44 ＋ 按鈕 42 ＝ 408）
    ///   ＋ hint 30 ≈ 532。⚠️ UIPanelSettings 是「依高度縮放、參考 640」，
    ///   所以邏輯高度永遠是 640，`.panel` 的 max-height 88% ＝ 563 —— 要壓在這底下。
    ///
    /// 清單項目在 Build 時建好一次（造型表是靜態的），Refresh 只改文字、class 和圖，
    /// 事件只註冊一次、不會越疊越多。
    /// </summary>
    public class WardrobePanel : MonoBehaviour
    {
        public static WardrobePanel Instance { get; private set; }

        public static WardrobePanel Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("WardrobeUI");
            DontDestroyOnLoad(go);
            return go.AddComponent<WardrobePanel>();
        }

        /// <summary>立繪原尺寸（像素畫，不縮放）。</summary>
        const int ArtW = 196, ArtH = 264;

        UIDocument doc;
        VisualElement root;
        bool built;
        UIAnim anim;      // 開關動效；「開著沒」看 anim.IsOpen，不看 display（見 UIAnim）

        // 左欄：每套一個項目（跟 Outfits.All() 同順序）
        VisualElement[] items;
        Label[] wearTags;

        // 右欄：預覽
        VisualElement portrait;
        Label nameLabel, descLabel;
        Button wearBtn;

        /// <summary>正在預覽的造型 id（不一定是身上那套）。</summary>
        string selected;

        void Awake()
        {
            Instance = this;
            doc = gameObject.AddComponent<UIDocument>();
            doc.panelSettings = Resources.Load<PanelSettings>("ui/UIPanelSettings");
            doc.sortingOrder = 12;
            if (doc.panelSettings == null)
                Debug.LogError("[WardrobePanel] 找不到 Resources/ui/UIPanelSettings");
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (anim != null && anim.IsOpen) UIState.ModalOpen = false;
        }

        void Update()
        {
            if (!built || root == null) return;
            if (anim.IsOpen && Input.GetKeyDown(KeyCode.Escape)) Close();
        }

        public void Open()
        {
            if (!built) Build();
            if (!built) return;
            anim.Show();                 // 淡入（邏輯上這一行就算開著，見 UIAnim）
            UIState.ModalOpen = true;
            Sfx.Play("ui-open");                                    // 音效：面板打開
            selected = Outfits.CurrentId();                         // 預設預覽身上那套
            GameArt.OnReady(Refresh);
        }

        public void Close()
        {
            anim?.Hide();                // 淡出只是視覺殘影，邏輯上這一行就算關了
            UIState.ModalOpen = false;
            Sfx.Play("ui-close");                                   // 音效：面板關閉
        }

        void Build()
        {
            root = doc.rootVisualElement;
            if (root == null) { Debug.LogError("[WardrobePanel] 沒有 rootVisualElement"); return; }
            root.styleSheets.Add(Resources.Load<StyleSheet>("ui/ShopManageStyle"));
            UiSkin.Apply(root);           // 8-bit 外觀（總開關在 UiSkin.Enabled）
            CjkFont.Apply(root);
            Sfx.BindClicks(root);         // 所有按鈕的 click 音（清單項目不是 Button，自己補）

            var dim = new VisualElement();
            dim.AddToClassList("dim");
            root.Add(dim);

            var panel = new VisualElement();
            panel.AddToClassList("panel");
            panel.style.width = 640;
            dim.Add(panel);

            var header = new VisualElement();
            header.AddToClassList("header");
            panel.Add(header);

            var title = new Label("衣櫃");
            title.AddToClassList("title");
            header.Add(title);

            var spacer = new VisualElement();
            spacer.AddToClassList("spacer");
            header.Add(spacer);

            var close = new Button(Close) { text = "×" };
            close.AddToClassList("close");
            header.Add(close);

            var body = new VisualElement();
            body.AddToClassList("wd-body");
            panel.Add(body);

            // ── 左欄：造型清單（只顯示名稱；身上那套標「穿著中」）
            var list = new VisualElement();
            list.AddToClassList("wd-list");
            body.Add(list);

            var all = Outfits.All();
            items = new VisualElement[all.Length];
            wearTags = new Label[all.Length];
            for (int i = 0; i < all.Length; i++)
            {
                string id = all[i].Id;                 // 迴圈變數要抓進閉包
                var item = new VisualElement();
                item.AddToClassList("wd-item");
                item.RegisterCallback<ClickEvent>(_ =>
                {
                    selected = id;                     // 只是預覽，不換裝
                    Sfx.Play("ui-click");              // 不是 Button，BindClicks 管不到
                    Refresh();
                });

                var nm = new Label(all[i].Name);
                nm.AddToClassList("wd-item-name");
                item.Add(nm);

                var tag = new Label("穿著中");
                tag.AddToClassList("wd-tag");
                item.Add(tag);

                list.Add(item);
                items[i] = item;
                wearTags[i] = tag;
            }

            // ── 右欄：大立繪＋名稱＋說明＋換上
            var preview = new VisualElement();
            preview.AddToClassList("wd-preview");
            body.Add(preview);

            var frame = new VisualElement();
            frame.AddToClassList("wd-frame");
            preview.Add(frame);

            portrait = new VisualElement();
            portrait.AddToClassList("wd-art");
            portrait.style.width = ArtW;
            portrait.style.height = ArtH;
            frame.Add(portrait);

            nameLabel = new Label();
            nameLabel.AddToClassList("wd-name");
            preview.Add(nameLabel);

            descLabel = new Label();
            descLabel.AddToClassList("wd-desc");
            preview.Add(descLabel);

            wearBtn = new Button(WearSelected);
            wearBtn.AddToClassList("btn");
            wearBtn.AddToClassList("wd-wear");
            preview.Add(wearBtn);

            UiSkin.Footer(panel, "關閉", "Esc").text = "點左邊預覽";

            anim = UIAnim.Pop(root, panel, dim);              // 淡入＋輕微放大，暗幕只淡入
            built = true;
        }

        /// <summary>按「換上」：把正在預覽的那套穿上。</summary>
        void WearSelected()
        {
            if (string.IsNullOrEmpty(selected) || selected == Outfits.CurrentId()) return;
            Outfits.Set(selected);
            Sfx.Play("cast", 0.7f);
            Refresh();
        }

        void Refresh()
        {
            if (!built) return;
            string cur = Outfits.CurrentId();
            var all = Outfits.All();
            if (string.IsNullOrEmpty(selected)) selected = cur;

            OutfitDef sel = null;
            for (int i = 0; i < all.Length; i++)
            {
                bool isSel = all[i].Id == selected;
                if (isSel) sel = all[i];
                items[i].EnableInClassList("wd-item--sel", isSel);
                wearTags[i].style.display = all[i].Id == cur ? DisplayStyle.Flex : DisplayStyle.None;
            }
            if (sel == null) { selected = cur; sel = OutfitCatalog.ById(cur); }

            // 立繪：找不到就留空框
            var sp = string.IsNullOrEmpty(sel.Portrait) ? null : GameArt.Portrait(sel.Portrait);
            portrait.style.backgroundImage = sp != null ? new StyleBackground(sp) : StyleKeyword.None;

            nameLabel.text = sel.Name;
            descLabel.text = sel.Desc;

            bool wearing = sel.Id == cur;
            wearBtn.text = wearing ? "穿著中" : "換上";
            wearBtn.SetEnabled(!wearing);
            wearBtn.EnableInClassList("btn-list", !wearing);     // 綠：可以換
            wearBtn.EnableInClassList("btn-buy", wearing);       // 藍：身上這套（停用）
        }
    }
}
