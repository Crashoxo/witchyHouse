using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>家具／裝飾的種類（店裡跟家裡共用的分類）。</summary>
    public enum FurnKind
    {
        Sale = 0,       // 販售桌（開店送的、不能收）
        Shelf,          // 靠牆貨架（前面要留走道）
        Table,          // 陳列桌（桌面上擺商品，不用靠牆、不留走道）
        Furniture,      // 一般家具（沙發、書櫃、鐘…）
        Lamp,           // 會發光的燈
        Decor,          // 小裝飾（自由座標、不擋路）
        Rug,            // 地毯（自由座標、平貼地板、排在所有東西底下）
    }

    /// <summary>可以擺在哪：會陳列商品的只能擺店裡；其他店裡、家裡都行。</summary>
    public enum PlaceRoom
    {
        ShopOnly = 0,
        ShopOrHome = 1,
    }

    /// <summary>
    /// 燈的光暈設定（半徑、顏色、最亮時的 alpha、閃爍幅度）。
    /// 光暈的**位置**跟著圖走，由 tools/gen_furniture8.py 量好寫在 <see cref="FurnitureArt8"/>（相對錨點、沒翻面）。
    /// </summary>
    public readonly struct LightSpec
    {
        public readonly float Radius;
        public readonly Color32 Color;
        public readonly float Strength;
        public readonly float Flicker;

        public LightSpec(float radius, Color32 color, float strength = 0.55f, float flicker = 0.12f)
        { Radius = radius; Color = color; Strength = strength; Flicker = flicker; }
    }

    /// <summary>
    /// 店裡與家裡共用的「家具／裝飾」查詢（房間無關）：把 <see cref="Furniture"/>（吃格子的）與
    /// <see cref="Decor"/>（自由座標的）兩份目錄當成一份來問。
    ///
    /// ── 佔地的約定 ──
    ///   吃格子的家具：佔 W×H 格，一格＝等距 64×32 的菱形（gx 往畫面右下、gy 往畫面左下）。
    ///   圖的正下方中央＝佔地的「前角」（最靠畫面下方那一點）；翻面＝左右鏡像，佔地寬深對調。
    ///   → <see cref="FootprintWorld"/> 給「前角在哪」就算得出佔地四邊形，不需要店裡的格盤。
    ///   自由座標的裝飾：沒有格子，<see cref="DecorFootprint"/> 給一個地上的小橢圓（給家裡擋路／排序參考）。
    /// </summary>
    public static class Furnishings
    {
        public const float CellW = 64f, CellH = 32f;

        public static bool IsKnown(string id) => Furniture.ById(id) != null || Decor.ById(id) != null;

        /// <summary>吃格子的（Furniture）還是自由座標的（Decor）。</summary>
        public static bool IsGrid(string id) => Furniture.ById(id) != null;

        public static string NameOf(string id) => Furniture.ById(id)?.Name ?? Decor.ById(id)?.Name ?? id;

        public static FurnKind KindOf(string id)
        {
            var f = Furniture.ById(id);
            if (f != null) return f.Kind;
            var d = Decor.ById(id);
            return d != null ? d.Kind : FurnKind.Decor;
        }

        public static PlaceRoom WhereOf(string id)
        {
            var f = Furniture.ById(id);
            if (f != null) return f.Where;
            return PlaceRoom.ShopOrHome;
        }

        public static bool CanPlaceAtHome(string id) => IsKnown(id) && WhereOf(id) == PlaceRoom.ShopOrHome;

        /// <summary>會擋路嗎：吃格子的全部會擋；裝飾、地毯不擋。</summary>
        public static bool Blocking(string id) => IsGrid(id);

        /// <summary>平貼地板（地毯）：排序壓在所有東西底下。</summary>
        public static bool Flat(string id) => KindOf(id) == FurnKind.Rug;

        public static LightSpec? LightOf(string id)
        {
            var f = Furniture.ById(id);
            if (f != null) return f.Light;
            return Decor.ById(id)?.Light;
        }

        /// <summary>
        /// 佔 w×h 格（已經是轉向後的寬深）、前角在 <paramref name="front"/> 的佔地四邊形（世界座標，順時針：後、右、前、左）。
        /// inset＝每邊往內縮幾格（碰撞用 ShopRoom.FurnitureInset 0.2；畫格子用 0）。跟 ShopRoom.FootprintPoly 同一個形狀。
        /// </summary>
        public static Vector2[] FootprintWorld(Vector2 front, int w, int h, float inset = 0f)
        {
            var ex = new Vector2(CellW / 2f, -CellH / 2f);    // gx +1
            var ey = new Vector2(-CellW / 2f, -CellH / 2f);   // gy +1
            // 前角 ＝ 格座標 (w, h)（相對後角 (0,0)）
            Vector2 G(float a, float b) => front + (a - w) * ex + (b - h) * ey;
            return new[] { G(inset, inset), G(w - inset, inset), G(w - inset, h - inset), G(inset, h - inset) };
        }

        /// <summary>自由座標裝飾在地上的橢圓（中心、半寬、半高）：依圖寬估（地毯整張都是）。</summary>
        public static (Vector2 Center, float Rx, float Ry) DecorFootprint(string id, Vector2 pos, float artWidth)
        {
            if (Flat(id)) return (pos + new Vector2(0f, artWidth * 0.25f), artWidth * 0.5f, artWidth * 0.25f);
            float rx = Mathf.Max(6f, artWidth * 0.32f);
            return (pos + new Vector2(0f, rx * 0.5f), rx, rx * 0.5f);
        }
    }
}
