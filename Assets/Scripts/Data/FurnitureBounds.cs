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
            { "sale_table", new ArtBox(140, 75, 6, 0, 103, 70) },
            { "shelf_arch", new ArtBox(174, 176, 66, 2, 170, 172) },
            { "shelf_back", new ArtBox(176, 182, 56, 4, 172, 178) },
            { "shelf_box", new ArtBox(176, 175, 62, 1, 172, 171) },
            { "shelf_cabinet", new ArtBox(128, 180, 40, 3, 124, 176) },
            { "shelf_cross", new ArtBox(176, 175, 66, 1, 172, 171) },
            { "shelf_curve", new ArtBox(224, 179, 106, 2, 220, 175) },
            { "shelf_deep", new ArtBox(228, 171, 106, 2, 224, 167) },
            { "shelf_drawer", new ArtBox(184, 183, 70, 3, 180, 179) },
            { "shelf_narrow", new ArtBox(188, 181, 86, 4, 184, 177) },
            { "shelf_peak", new ArtBox(164, 177, 52, 2, 160, 173) },
            { "shelf_plank", new ArtBox(184, 183, 64, 4, 180, 179) },
            { "shelf_round", new ArtBox(168, 174, 56, 3, 164, 170) },
            { "shelf_scallop", new ArtBox(192, 179, 70, 4, 188, 175) },
            { "shelf_slat", new ArtBox(204, 178, 86, 1, 200, 174) },
            { "shelf_tall", new ArtBox(124, 181, 42, 2, 120, 177) },
            { "shelf_two", new ArtBox(172, 179, 62, 1, 168, 175) },
        };

        /// <summary>查不到就回 false（呼叫端退回用整張圖的矩形）。</summary>
        public static bool TryGet(string id, out ArtBox box) => Table.TryGetValue(id, out box);
    }
}
