using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>鎮上的一位角色。</summary>
    public class CandyNpc
    {
        public string Id;          // 節點名（也當識別用）
        public string Name;        // 顯示名字（對話框、提示都用它）
        public string Art;         // Resources/candy/<Art>.png
        public float X, Y;
        public float Scale;        // 原圖縮到畫面上的比例（原圖是立繪尺寸，直接放會比女巫大好幾倍）
        public string[] Lines;     // 走近按 E 講的話
        public string ShopTitle;   // 有填就是商店：按 E 開購買面板
    }

    /// <summary>一棟建築／一件裝飾（都是站在地上的圖，錨點在腳底吃 YSort）。</summary>
    public class CandyProp
    {
        public string Art;
        public float X, Y, Scale;
    }

    /// <summary>
    /// 糖果鎮（森林北邊那張地圖）的「內容」資料：住在鎮上的角色、他們賣什麼、路人怎麼晃。
    ///
    /// 座標是糖果鎮場景的世界座標（Ground 3200×1745、原點在地圖正中央的噴泉）。
    /// 場景檔只有骨架，這裡的東西全部由 CandyTown.cs 在執行期擺出來。
    /// </summary>
    public static class Candy
    {
        public static readonly CandyNpc[] Npcs =
        {
            new() { Id = "tamer", Name = "軟糖鱷馴養師", Art = "tamer", X = -380, Y = 60, Scale = 0.37f,
                    ShopTitle = "軟糖鱷商行",
                    Lines = new[]
                    {
                        "歡迎來到糖果鎮！這些軟糖鱷是我養的，別怕，牠們只咬糖。",
                        "你手上那些藥水挺有意思的——不過先看看我的貨吧，都是森林那邊買不到的。",
                    } },
            new() { Id = "guard", Name = "時晶守衛", Art = "guard", X = 300, Y = -40, Scale = 0.45f,
                    Lines = new[]
                    {
                        "止步……不，抱歉，看你不像來搗亂的。",
                        "我守著這座噴泉，它下面就是糖李礦坑的入口。",
                        "想下去？先去馴養師那裡買張地圖吧，沒有地圖的人都繞回原地了。",
                    } },
            new() { Id = "sproutling", Name = "小芽苗", Art = "sproutling", X = -140, Y = -290, Scale = 0.30f,
                    Lines = new[]
                    {
                        "（它輕輕晃了晃頭上的花。）",
                        "……嗯？你是森林來的女巫嗎？我聞得到藥草的味道。",
                        "這裡的土是糖做的，種不出草藥喔。",
                    } },
        };

        /// <summary>馴養師賣的東西（買進來可以擺自己店裡賣給顧客賺差價）。</summary>
        public static readonly (string Name, int Price)[] Goods =
        {
            ("焦糖蘋果棒", 45), ("鱷魚軟糖袋", 60), ("永恆彩球糖", 90),
            ("糖李礦坑地圖", 150), ("妖精粉小袋", 200), ("時晶法杖", 400),
        };

        /// <summary>
        /// 鎮上晃來晃去的小東西（軟糖鱷與芽苗）。
        /// ⚠️ 縮放要照各自原圖尺寸回推身高（女巫約 68px），不能三隻用同一個值 ——
        ///    同樣的 Scale 會讓大鱷魚變成最小的那隻。
        /// </summary>
        public static readonly (string Art, float Scale)[] Critters =
        {
            ("gingerbread-front", 0.50f), ("gator-small", 0.45f),
            ("gingerbread-left", 0.50f),  ("gator-medium", 0.40f),
            ("gator-large", 0.42f),       ("gingerbread-right", 0.50f),
        };

        /// <summary>路人的路線（繞著中央廣場走，都落在鋪面上）。</summary>
        public static readonly Vector2[] Walk =
        {
            new(-800, 60), new(0, 300), new(800, 60),
            new(450, -60), new(0, -300), new(-450, -60),
        };

        /// <summary>同時最多幾隻路人。</summary>
        public const int Crowd = 5;

        /// <summary>
        /// 鎮上的建築。**地圖不是一張大圖放大來的** —— 地面是糖果磚拼的，房子是一棟棟擺上去的，
        /// 所以放大也不會糊。位置繞著中央廣場（1000×700）與十字大道（寬 200）安排。
        /// </summary>
        public static readonly CandyProp[] Buildings =
        {
            new() { Art = "b-candyshop",     X = -620,  Y = 190,  Scale = 0.95f },
            new() { Art = "b-bakery",        X = 640,   Y = 190,  Scale = 0.95f },
            new() { Art = "b-house1",        X = -640,  Y = -300, Scale = 0.95f },
            new() { Art = "b-house2",        X = 660,   Y = -300, Scale = 0.95f },
            new() { Art = "b-castle",        X = 0,     Y = 760,  Scale = 1.0f },
            new() { Art = "b-house-orchard", X = -1120, Y = 560,  Scale = 0.9f },
            new() { Art = "b-ruins",         X = 1150,  Y = -560, Scale = 0.9f },
        };

        /// <summary>街上的小東西（樹、灌木、水晶、糖果）。</summary>
        public static readonly CandyProp[] Props =
        {
            new() { Art = "p-lollitree",  X = -1250, Y = 250,  Scale = 1.0f },
            new() { Art = "p-lollitree",  X = 1250,  Y = 250,  Scale = 1.0f },
            new() { Art = "p-lollitree",  X = -1000, Y = -120, Scale = 1.0f },
            new() { Art = "p-lollitree",  X = 1000,  Y = -120, Scale = 1.0f },
            new() { Art = "p-grove",      X = -1400, Y = -700, Scale = 0.9f },
            new() { Art = "p-grove",      X = 1380,  Y = 700,  Scale = 0.9f },
            new() { Art = "p-bushrow",    X = -300,  Y = 430,  Scale = 1.0f },
            new() { Art = "p-bushrow",    X = 320,   Y = 430,  Scale = 1.0f },
            new() { Art = "p-bush",       X = -560,  Y = -60,  Scale = 1.0f },
            new() { Art = "p-bush",       X = 560,   Y = -60,  Scale = 1.0f },
            new() { Art = "p-crystal",    X = -860,  Y = 620,  Scale = 1.0f },
            new() { Art = "p-crystal2",   X = 880,   Y = 620,  Scale = 1.0f },
            new() { Art = "p-rock",       X = -1180, Y = -420, Scale = 1.0f },
            new() { Art = "p-stump",      X = 1180,  Y = -420, Scale = 1.0f },
            new() { Art = "p-cloud",      X = -420,  Y = 880,  Scale = 1.0f },
            new() { Art = "p-cloud",      X = 460,   Y = 880,  Scale = 1.0f },
            new() { Art = "p-peppermint", X = -180,  Y = 120,  Scale = 0.5f },
            new() { Art = "p-chest",      X = 230,   Y = 150,  Scale = 0.5f },
            new() { Art = "p-cherries",   X = -260,  Y = -170, Scale = 0.6f },
            new() { Art = "p-candycane",  X = 250,   Y = -180, Scale = 1.0f },
            new() { Art = "p-mint",       X = -60,   Y = -420, Scale = 0.8f },
        };
    }
}
