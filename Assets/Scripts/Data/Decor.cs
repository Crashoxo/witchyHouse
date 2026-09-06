namespace WitchShop.Data
{
    public class DecorDef
    {
        public string Id;
        public string Name;
        public int Price;
        /// <summary>
        /// 顯示縮放。0 ＝用 DecorRoom 的 decorScale（0.4）—— 最早那十六款是從大張 Gemini 圖
        /// 切下來的，不縮會比房間還大。**新的美術直接畫在遊戲尺度上的就標 Scale = 1。**
        /// </summary>
        public float Scale;
    }

    /// <summary>
    /// 裝飾品「內容」資料：花店販售的裝飾（id / 中文名 / 售價）。
    /// 擁有/擺放的狀態（owned/placed）在 DecorCatalog.cs。
    /// </summary>
    public static class Decor
    {
        public static readonly DecorDef[] Catalog =
        {
            new() { Id = "succulent",         Name = "多肉盆栽",   Price = 40 },
            new() { Id = "daisypot",          Name = "雛菊小盆",   Price = 45 },
            new() { Id = "violetpot",         Name = "紫羅蘭盆",   Price = 45 },
            new() { Id = "birdcage_small",    Name = "花鳥籠",     Price = 90 },
            new() { Id = "bonsai",            Name = "松柏盆景",   Price = 150 },
            new() { Id = "ivy_hanging",       Name = "常春藤吊籃", Price = 80 },
            new() { Id = "roses_vase",        Name = "玫瑰花瓶",   Price = 120 },
            new() { Id = "lily_vase",         Name = "百合花瓶",   Price = 130 },
            new() { Id = "sunflower_vase",    Name = "向日葵瓶",   Price = 110 },
            new() { Id = "autumn_vase",       Name = "秋葉銅瓶",   Price = 160 },
            new() { Id = "potted_fern",       Name = "蕨葉盆栽",   Price = 180 },
            new() { Id = "window_box",        Name = "紫花窗台",   Price = 140 },
            new() { Id = "birdcage_large",    Name = "大花鳥籠",   Price = 220 },
            new() { Id = "blue_urn",          Name = "藍花石甕",   Price = 260 },
            new() { Id = "wildflower_basket", Name = "野花籃",     Price = 300 },
            new() { Id = "flower_case",       Name = "星光花櫃",   Price = 500 },
            // PixelLab 出的三個展示架。⚠️ 雖然跟貨架畫在同一個 72px 畫布上，但畫的是**小擺飾**，
            // Scale 1 會讓藥水瓶跟女巫一樣高（試過）—— 0.45 才是桌上擺飾該有的大小。
            new() { Id = "herb_shelf",    Name = "乾燥花草架", Price = 150, Scale = 0.45f },
            new() { Id = "crystal_shelf", Name = "水晶展示架", Price = 200, Scale = 0.45f },
            new() { Id = "potion_shelf",  Name = "藥水展示架", Price = 240, Scale = 0.45f },
        };

        public static DecorDef ById(string id)
        {
            foreach (var d in Catalog) if (d.Id == id) return d;
            return null;
        }
    }
}
