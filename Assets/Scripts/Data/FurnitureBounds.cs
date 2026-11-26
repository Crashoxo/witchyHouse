using System.Collections.Generic;

namespace WitchShop.Data
{
    /// <summary>一張家具圖裡「真正畫到東西」的範圍（座標原點在圖的左下角）。</summary>
    public readonly struct ArtBox
    {
        public readonly float ImgW, ImgH;      // 整張圖的尺寸
        public readonly float X0, Y0, X1, Y1;  // 不透明範圍

        public ArtBox(float imgW, float imgH, float x0, float y0, float x1, float y1)
        { ImgW = imgW; ImgH = imgH; X0 = x0; Y0 = y0; X1 = x1; Y1 = y1; }
    }

    /// <summary>
    /// 家具圖的不透明範圍表 —— **自動產生，不要手改**。
    /// 產生器：`tools/gen_furniture_bounds.py`（換了家具美術要重跑）。
    ///
    /// 為什麼要這張表：家具的 PNG 有很大一塊透明邊，而且不是置中的
    /// （shelf_box 圖寬 176，實際畫到的只有 x=62..171）。判「貨架會不會穿牆」時
    /// 拿整張圖的矩形去比，左邊會被空白誤判成超出去、右邊又會少算。
    /// </summary>
    public static class FurnitureBounds
    {
        static readonly Dictionary<string, ArtBox> Table = new()
        {
            { "sale_table", new ArtBox(128, 79, 0, 2, 97, 79) },
            { "shelf_arch", new ArtBox(166, 177, 52, 6, 166, 177) },
            { "shelf_back", new ArtBox(172, 185, 51, 6, 172, 185) },
            { "shelf_box", new ArtBox(166, 178, 52, 6, 166, 178) },
            { "shelf_cabinet", new ArtBox(172, 183, 51, 6, 172, 183) },
            { "shelf_cross", new ArtBox(166, 179, 50, 6, 166, 179) },
            { "shelf_curve", new ArtBox(164, 182, 49, 7, 164, 182) },
            { "shelf_deep", new ArtBox(186, 181, 60, 1, 186, 181) },
            { "shelf_drawer", new ArtBox(174, 185, 52, 5, 174, 185) },
            { "shelf_narrow", new ArtBox(160, 177, 47, 8, 160, 177) },
            { "shelf_peak", new ArtBox(174, 176, 51, 6, 174, 176) },
            { "shelf_plank", new ArtBox(174, 184, 50, 5, 174, 184) },
            { "shelf_round", new ArtBox(166, 174, 52, 6, 166, 174) },
            { "shelf_scallop", new ArtBox(168, 181, 51, 6, 168, 181) },
            { "shelf_slat", new ArtBox(166, 179, 50, 6, 166, 179) },
            { "shelf_tall", new ArtBox(106, 184, 18, 6, 106, 184) },
            { "shelf_two", new ArtBox(168, 179, 51, 6, 168, 179) },
        };

        /// <summary>查不到就回 false（呼叫端退回用整張圖的矩形）。</summary>
        public static bool TryGet(string id, out ArtBox box) => Table.TryGetValue(id, out box);
    }
}
