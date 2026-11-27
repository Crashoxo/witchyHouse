using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 從 id 生出一件家具／裝飾／燈的畫面物件 —— 店裡（ShopRoomView）跟家裡共用的**唯一**入口，跟格盤無關。
    ///
    /// 生出來的結構：
    ///   根物件（position ＝落腳點＝圖的正下方中央；吃格子的家具＝佔地前角，RoomLayout.AnchorPos 算的）
    ///     ├─ "art"   SpriteRenderer（第一個子物件！佈置模式的 HitTest／Tint 用 GetComponentInChildren 拿它）
    ///     │           往上推半個圖高、翻面＝scale.x 取負；接地影子已經畫在圖裡（半透明）
    ///     └─ "light" FurnitureLight（有 LightSpec 的燈才有；位置照 FurnitureArt8 量的點，翻面時 X 取負）
    /// 排序：art.sortingOrder ＝ <see cref="SortOrder"/>（-落腳點 y；地毯固定 <see cref="FlatOrder"/>）。
    /// 架上商品（ShopRoomView.SpawnGoods）會再掛在根物件底下、排在 art 之後。
    /// </summary>
    public static class FurnishingVisual
    {
        /// <summary>地毯的排序：在房間底圖（-10000）之上、所有站著的東西之下。</summary>
        public const int FlatOrder = -9000;

        public static int SortOrder(string id, Vector2 pos) =>
            Furnishings.Flat(id) ? FlatOrder : Mathf.RoundToInt(-pos.y);

        /// <summary>
        /// 生一件（沒有圖回 null）。
        /// </summary>
        /// <param name="id">Furniture 或 Decor 的 id</param>
        /// <param name="pos">落腳點（世界座標）</param>
        /// <param name="flip">左右鏡像</param>
        /// <param name="parent">掛在誰底下（null＝場景根）</param>
        /// <param name="lightMode">燈的模式：店裡 Shop、家裡 NightOnly</param>
        public static GameObject Create(string id, Vector2 pos, bool flip, Transform parent = null,
                                        FurnitureLight.Mode lightMode = FurnitureLight.Mode.Shop)
        {
            bool grid = Furniture.ById(id) != null;
            var sp = grid ? GameArt.FurnitureArt(id) : GameArt.Decoration(id);
            if (sp == null) return null;
            float scale = grid ? 1f : GameArt.DecorScale(id);

            var go = new GameObject(grid ? $"furn-{id}" : $"decor-{id}");
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = new Vector3(pos.x, pos.y, 0f);

            var art = new GameObject("art");
            art.transform.SetParent(go.transform, false);
            art.transform.localScale = new Vector3(flip ? -scale : scale, scale, 1f);
            art.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * scale, 0f);
            var sr = art.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = SortOrder(id, pos);

            var spec = Furnishings.LightOf(id);
            if (spec.HasValue)
                foreach (var p in FurnitureArt8.LightPoints(id, sp.rect.width, sp.rect.height))
                    FurnitureLight.Attach(go, new Vector2((flip ? -p.x : p.x) * scale, p.y * scale), spec.Value, lightMode);
            return go;
        }

        /// <summary>這件物件的圖（"art" 的 SpriteRenderer）。</summary>
        public static SpriteRenderer ArtOf(GameObject go)
        {
            if (go == null) return null;
            var t = go.transform.Find("art");
            return t != null ? t.GetComponent<SpriteRenderer>() : null;
        }
    }
}
