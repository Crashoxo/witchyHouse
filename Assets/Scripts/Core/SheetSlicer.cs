using UnityEngine;

namespace WitchShop.Core
{
    /// <summary>
    /// 走圖切格。獨立成一個檔是因為這裡藏著整個移植最容易靜默出錯的地方：
    ///
    /// ⚠️ **Cocos 與 Unity 的 rect 原點上下相反。**
    ///    Cocos  `SpriteFrame.rect` 的 y 從圖的**左上角**往下算。
    ///    Unity  `Sprite.Create` 的 rect y 從圖的**左下角**往上算。
    ///
    ///    原專案寫 `new Rect(c*cw, r*ch, cw, ch)`（r＝第幾列，從上往下數）。
    ///    照抄到 Unity 會把列整個上下翻轉 —— 村民的「朝下」會變成「朝上」、
    ///    女巫圖集的走路列會讀到施法列。畫面上「有在動」，只是動錯，非常難發現。
    ///
    ///    所以一律走 <see cref="Cell"/>，不要在別處自己算 Rect。
    /// </summary>
    public static class SheetSlicer
    {
        /// <summary>所有切出來的 Sprite 都用 1 單位 = 1 像素（見 PortNotes.md）。</summary>
        public const float PixelsPerUnit = 1f;

        static readonly Vector2 Center = new(0.5f, 0.5f);

        /// <summary>
        /// 腳底樞紐（格子的底邊中央）。**只給女巫用**。
        ///
        /// 專案的通例是「圖掛在子物件上往上推半身高」（見 PortNotes.md 的腳底錨點），
        /// 但女巫的 <c>SpriteRenderer</c> 就掛在 <c>Player</c> 本身、沒有那個子物件，
        /// 所以改成把樞紐直接放到格子底邊 —— 效果一樣（<c>position</c> ＝ 落腳點），
        /// 而且六張場景的場景檔與所有呼叫端都不用動。
        ///
        /// 對齊的是**格子的底邊**而不是鞋底，跟 Cocos 版的錨點 `(0.5, 0)` 完全一致
        /// （鞋底到底邊還有幾個像素的透明邊，見 <c>CharacterAnimator.FootPad</c>）。
        /// </summary>
        public static readonly Vector2 Foot = new(0.5f, 0f);

        /// <summary>
        /// 取走圖的第 (col, row) 格。**row 照 Cocos 的習慣從上往下數**（0 ＝最上面那列），
        /// 內部才轉成 Unity 的座標，呼叫端可以直接沿用原專案的列編號。
        /// </summary>
        /// <param name="tex">整張走圖</param>
        /// <param name="col">第幾欄（從左往右，0 起）</param>
        /// <param name="row">第幾列（**從上往下**，0 起）</param>
        /// <param name="cols">總欄數</param>
        /// <param name="rows">總列數</param>
        /// <param name="pivot">樞紐（null ＝正中心）。女巫傳 <see cref="Foot"/>。</param>
        public static Sprite Cell(Texture2D tex, int col, int row, int cols, int rows,
                                  Vector2? pivot = null)
        {
            float cw = (float)tex.width / cols;
            float ch = (float)tex.height / rows;
            // ↓ 這一行就是上下翻轉的修正：Cocos 的第 row 列 = Unity 的 (rows-1-row) 列
            float y = tex.height - (row + 1) * ch;
            return Sprite.Create(tex, new Rect(col * cw, y, cw, ch),
                                 pivot ?? Center, PixelsPerUnit, 0, SpriteMeshType.FullRect);
        }

        /// <summary>橫向 strip 的第 i 幀（單列，格寬高固定 —— 表情動畫用）。</summary>
        public static Sprite StripCell(Texture2D tex, int i, int frameW, int frameH)
        {
            // strip 只有一列，但 y 一樣要從下往上算：整張高度扣掉一格高
            return Sprite.Create(tex, new Rect(i * frameW, tex.height - frameH, frameW, frameH),
                                 Center, PixelsPerUnit, 0, SpriteMeshType.FullRect);
        }

        /// <summary>整張圖當一個 Sprite（背景、單張道具圖用）。</summary>
        public static Sprite Whole(Texture2D tex, Vector2? pivot = null) =>
            Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height),
                          pivot ?? Center, PixelsPerUnit, 0, SpriteMeshType.FullRect);

        /// <summary>切一整列（回傳該列的所有欄）。row 一樣是從上往下數。</summary>
        public static Sprite[] Row(Texture2D tex, int row, int cols, int rows,
                                   Vector2? pivot = null)
        {
            var arr = new Sprite[cols];
            for (int c = 0; c < cols; c++) arr[c] = Cell(tex, c, row, cols, rows, pivot);
            return arr;
        }
    }
}
