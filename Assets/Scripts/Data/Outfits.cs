namespace WitchShop.Data
{
    public class OutfitDef
    {
        /// <summary>存檔用的 id。</summary>
        public string Id;
        /// <summary>衣櫃面板顯示的名稱。</summary>
        public string Name;
        /// <summary>一句話說明。</summary>
        public string Desc;
        /// <summary>Resources/witch8/&lt;Art&gt;.png 的檔名；空字串＝預設的 base.png。</summary>
        public string Art;
        /// <summary>立繪：Resources/portraits/&lt;Portrait&gt;.png；空字串＝沒有立繪（畫個色塊代替）。</summary>
        public string Portrait;
    }

    /// <summary>
    /// 造型（換裝）「內容」資料。
    ///
    /// 一套造型 ＝ 一整張女巫圖集 Resources/witch8/&lt;Art&gt;.png（站姿/走路/跑步/施法）
    /// ＋ 一張 &lt;Art&gt;-sleep.png。**不是把衣服疊成圖層** —— 帽子與披風本身就是角色輪廓，
    /// 而且只有幾套完整造型，分層那種「多部位排列組合」的好處用不到。
    ///
    /// Art = "" ＝預設造型，用 witch8/base.png。
    ///
    /// ⚠️ 叫 OutfitCatalog 而不是 Outfits，是為了跟 Core.Outfits（「現在穿哪一套」的
    ///    狀態）區分開。兩個都叫 Outfits 的話，Core 命名空間裡的檔案會優先抓到自己
    ///    那個，而且錯誤訊息（method group）完全看不出是撞名。同 Decor / DecorCatalog。
    /// </summary>
    public static class OutfitCatalog
    {
        // ⚠️ 2026-08-07 換角色後，換裝改成「把緞邊的緋紅改色」（黑袍本身不動）——
        //    新角色是黑袍，舊那套「紫色轉色相」沒東西可轉。Id 保持原樣，存檔才不會失效。
        public static readonly OutfitDef[] All =
        {
            new() { Id = "default", Name = "緋紅緞邊", Art = "",      Portrait = "outfit8-default",
                    Desc = "黑帽黑袍配暗紅緞帶與滾邊，出門採集最順手的一套。" },
            new() { Id = "green",   Name = "苔綠緞邊", Art = "green", Portrait = "outfit8-green",
                    Desc = "緞帶染成森林苔綠，走在樹影底下幾乎看不見人。" },
            new() { Id = "brown",   Name = "琥珀緞邊", Art = "brown", Portrait = "outfit8-brown",
                    Desc = "琥珀金的緞帶與滾邊，適合遠行到糖果鎮進貨。" },
            new() { Id = "ivory",   Name = "霜白緞邊", Art = "ivory", Portrait = "outfit8-ivory",
                    Desc = "素白緞帶，調配藥水時最不怕沾上藥漬。" },
        };

        public static OutfitDef ById(string id)
        {
            foreach (var o in All) if (o.Id == id) return o;
            return All[0];
        }
    }
}
