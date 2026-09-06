using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 現在穿哪一套造型（純資料）。
    ///
    /// 換裝的實際效果只有一件事：叫 GameArt.ApplyOutfit() 換掉那批姿勢圖。之後所有拿
    /// 女巫圖的地方（走路、採集、澆水、摘花、施法、睡覺）都是透過 GameArt 的 accessor 拿，
    /// 所以**呼叫端一個都不用改**。
    ///
    /// ⚠️ 一套造型 ＝ 一整張改色版的圖集（witch8/&lt;art&gt;.png），不是把衣服疊成圖層 ——
    ///    帽子與披風本身就是角色輪廓，分層那種「多部位排列組合」的好處用不到。
    /// </summary>
    public static class Outfits
    {
        const string Key = "witch.outfit";

        static string current;

        static string Current
        {
            get
            {
                if (current == null)
                {
                    var v = SaveManager.GetString(Key);
                    // 防壞檔：認不得的 id 就回預設
                    current = !string.IsNullOrEmpty(v) && OutfitCatalog.ById(v).Id == v
                              ? v : OutfitCatalog.All[0].Id;
                }
                return current;
            }
        }

        public static OutfitDef[] All() => OutfitCatalog.All;
        public static string CurrentId() => Current;
        public static OutfitDef CurrentDef() => OutfitCatalog.ById(Current);

        /// <summary>換上某一套（id 認不得就當預設）。</summary>
        public static void Set(string id)
        {
            var def = OutfitCatalog.ById(id);
            current = def.Id;
            SaveManager.SetString(Key, current);
            GameArt.ApplyOutfit(def.Art);
        }

        /// <summary>
        /// 把存檔裡那套套用到美術上。**每個場景載入時要呼叫一次**
        /// （PlayerController.Awake）—— GameArt 的造型圖不像資料那樣跨場景留著。
        /// </summary>
        public static void Apply() => GameArt.ApplyOutfit(OutfitCatalog.ById(Current).Art);
    }
}
