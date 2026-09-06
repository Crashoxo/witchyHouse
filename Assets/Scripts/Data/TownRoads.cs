using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>
    /// 城鎮路點 —— 給 TownFolk 當村民的走動目標。
    ///
    /// 路面已經烤進 town-ground.png，場景裡沒有路面節點，所以這份清單是原專案用
    /// tools/bake_town_roads.py 從那張小地圖產生的：只取「四周至少 3 格也是路」的格
    /// （＝路的內部，村民不會貼著路邊走），再以曼哈頓距離 >= 3 格稀疏化。
    ///
    /// ⚠️ 改地圖之後要重跑原專案那支腳本，再把結果搬過來。
    /// </summary>
    public static class TownRoads
    {
        /// <summary>110 個路點。</summary>
        public static readonly Vector2[] Walk =
        {
            new(-32f, 992f), new(96f, 928f), new(-96f, 864f), new(32f, 800f),
            new(-1184f, 672f), new(-992f, 672f), new(-800f, 672f), new(-608f, 672f),
            new(-416f, 672f), new(-224f, 672f), new(-32f, 672f), new(160f, 672f),
            new(352f, 672f), new(544f, 672f), new(736f, 672f), new(864f, 608f),
            new(-1248f, 544f), new(-1056f, 544f), new(-864f, 544f), new(-672f, 544f),
            new(-480f, 544f), new(-288f, 544f), new(-96f, 544f), new(96f, 544f),
            new(288f, 544f), new(480f, 544f), new(672f, 544f), new(1376f, 544f),
            new(800f, 480f), new(-1184f, 416f), new(-32f, 416f), new(928f, 416f),
            new(1440f, 416f), new(96f, 352f), new(-160f, 288f), new(1248f, 288f),
            new(-32f, 224f), new(160f, 224f), new(1376f, 224f), new(-224f, 160f),
            new(1184f, 160f), new(224f, 96f), new(1312f, 96f), new(-1504f, 32f),
            new(-1312f, 32f), new(-1120f, 32f), new(-928f, 32f), new(-736f, 32f),
            new(-544f, 32f), new(-352f, 32f), new(-160f, 32f), new(352f, 32f),
            new(544f, 32f), new(736f, 32f), new(928f, 32f), new(1440f, 32f),
            new(160f, -32f), new(1056f, -32f), new(1248f, -32f), new(-1440f, -96f),
            new(-1248f, -96f), new(-1056f, -96f), new(-864f, -96f), new(-672f, -96f),
            new(-480f, -96f), new(-288f, -96f), new(288f, -96f), new(480f, -96f),
            new(672f, -96f), new(864f, -96f), new(1376f, -96f), new(-160f, -160f),
            new(32f, -160f), new(160f, -224f), new(1312f, -224f), new(-224f, -288f),
            new(-32f, -288f), new(1440f, -288f), new(96f, -352f), new(-800f, -416f),
            new(1312f, -416f), new(-1440f, -480f), new(-1248f, -480f), new(-672f, -480f),
            new(-480f, -480f), new(-288f, -480f), new(-96f, -480f), new(160f, -480f),
            new(352f, -480f), new(544f, -480f), new(736f, -480f), new(928f, -480f),
            new(1440f, -480f), new(-1120f, -544f), new(32f, -544f), new(1056f, -544f),
            new(1248f, -544f), new(-1376f, -608f), new(-736f, -608f), new(-544f, -608f),
            new(-352f, -608f), new(-160f, -608f), new(224f, -608f), new(416f, -608f),
            new(608f, -608f), new(800f, -608f), new(1376f, -608f), new(1312f, -736f),
            new(1440f, -800f), new(1376f, -928f),
        };
    }

    /// <summary>地圖邊界上的傳送點（走出去換場景的那個「門」）。</summary>
    public class EdgePortal
    {
        public string Scene;   // 這一張地圖
        public string Side;    // 走出哪一側：left / right / top / bottom
        public string To;      // 走出去會到哪個場景
        public float At;       // 傳送點在邊上的位置（左右側＝y、上下側＝x）
        public float Span;     // 門的半寬（像素）
    }

    /// <summary>
    /// 走出地圖邊界會去哪裡。
    ///
    /// 原本走到那一側的**任何地方**都會換場景，玩家看不出邊界哪裡能走；改成整條邊只有
    /// 一個定點會傳送。這裡定的是「那個點在邊上的位置」，Span＝從那個點往兩邊各多寬算門內。
    ///
    /// ⚠️ Scene / To 用的是**原 Cocos 的場景名**（main / town / shop / brew / garden / candy）。
    ///    Unity 的場景檔也沿用同樣的檔名，這份資料與 GameArt 的分區載入才能原封不動用。
    /// </summary>
    public static class Portals
    {
        public static readonly EdgePortal[] All =
        {
            // 森林東側 → 城鎮：玩家出生在 (0,0)，這一段東側沒有樹擋著
            new() { Scene = "main", Side = "right", To = "town", At = 0f, Span = 80f },
            // 森林北側 → 糖果鎮（森林上面那張地圖）
            new() { Scene = "main", Side = "top", To = "candy", At = 0f, Span = 100f },
            // 城鎮西側 → 森林：對準往西的泥土路 (y=-40)，也是玩家進城的抵達點
            new() { Scene = "town", Side = "left", To = "main", At = -40f, Span = 80f },
            // ⚠️ 店內沒有邊界出口：房間是等距菱形地板，改用地板上的門（見 Doorways）
            // 糖果鎮南側 → 回森林
            new() { Scene = "candy", Side = "bottom", To = "main", At = 0f, Span = 160f },
        };

        /// <summary>某個場景的所有邊界出口（可以有好幾個）。</summary>
        public static System.Collections.Generic.List<EdgePortal> Of(string scene)
        {
            var outList = new System.Collections.Generic.List<EdgePortal>();
            foreach (var p in All) if (p.Scene == scene) outList.Add(p);
            return outList;
        }
    }
}
