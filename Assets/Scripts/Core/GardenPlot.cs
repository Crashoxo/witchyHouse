using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 一塊花圃的畫面：土壤磚（乾/濕）＋ 上面長的花 ＋ 缺水提醒 ＋ 操作後的小提示。
    /// 資料在 Garden（本檔只負責畫）。
    /// </summary>
    public class GardenPlot : MonoBehaviour
    {
        /// <summary>這是第幾格（對應 Garden 的 index）。</summary>
        public int index;

        SpriteRenderer soil;
        SpriteRenderer plant;
        GameObject thirsty;      // 「缺水」提醒

        public void Init(int i, Vector2 pos)
        {
            index = i;
            transform.position = new Vector3(pos.x, pos.y, 0f);

            var soilGo = new GameObject("soil");
            soilGo.transform.SetParent(transform, false);
            soilGo.transform.localScale = new Vector3(GardenData.PlotScale, GardenData.PlotScale, 1f);
            soil = soilGo.AddComponent<SpriteRenderer>();
            soil.sortingOrder = Mathf.RoundToInt(-pos.y) - 1;

            var plantGo = new GameObject("plant");
            plantGo.transform.SetParent(transform, false);
            // 從磚面偏下一點長出來（同原版的 -6）
            plantGo.transform.localPosition = new Vector3(0f, -6f, 0f);
            plantGo.transform.localScale = new Vector3(GardenData.FlowerScale, GardenData.FlowerScale, 1f);
            plant = plantGo.AddComponent<SpriteRenderer>();
            plant.sortingOrder = Mathf.RoundToInt(-pos.y);

            BuildThirsty();
            Refresh();
        }

        public void Refresh()
        {
            var v = Garden.View(index);

            soil.sprite = GameArt.Soil(v.Wet);

            var f = v.Empty ? null : GameArt.Flower(v.Art, v.Stage, v.Wilting);
            plant.sprite = f;
            plant.gameObject.SetActive(f != null);
            if (f != null)
            {
                // 花的圖是從走圖切出來的，錨點在中心 → 往上推半個高度才像長在土上
                plant.transform.localPosition =
                    new Vector3(0f, -6f + f.rect.height * 0.5f * GardenData.FlowerScale, 0f);
            }

            if (thirsty != null) thirsty.SetActive(Garden.NeedsWater(index));
        }

        void BuildThirsty()
        {
            thirsty = new GameObject("thirsty");
            thirsty.transform.SetParent(transform, false);
            thirsty.transform.localPosition = new Vector3(0f, 46f, 0f);

            var tm = thirsty.AddComponent<TextMesh>();
            tm.text = "缺水";
            tm.fontSize = 32;
            tm.characterSize = 4f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color32(140, 200, 255, 255);

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                thirsty.GetComponent<MeshRenderer>().material = font.material;
            }
            thirsty.GetComponent<MeshRenderer>().sortingOrder = 9300;
            thirsty.SetActive(false);
        }

        /// <summary>操作後在花圃上方冒一行字（種下了/澆好水了/收成…）。</summary>
        public void Popup(string msg)
        {
            var go = new GameObject("popup");
            go.transform.position = transform.position + new Vector3(0f, 30f, 0f);

            var tm = go.AddComponent<TextMesh>();
            tm.text = msg;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = new Color32(255, 246, 214, 255);

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                go.GetComponent<MeshRenderer>().material = font.material;
            }
            go.GetComponent<MeshRenderer>().sortingOrder = 9500;

            go.AddComponent<FloatAway>().Begin(new Vector3(0f, 40f, 0f), 1.1f, 0.5f);
        }

        /// <summary>
        /// 灑水特效：從女巫手上壺口的方向噴幾滴水過來。
        /// </summary>
        public void PlayWater(float fromDx, float fromDy)
        {
            for (int i = 0; i < 5; i++)
            {
                var go = new GameObject("drop");
                go.transform.position = transform.position + new Vector3(
                    fromDx * 0.7f + (Random.value - 0.5f) * 14f,
                    fromDy * 0.7f + (Random.value - 0.5f) * 10f + 20f, 0f);

                var sr = go.AddComponent<SpriteRenderer>();
                sr.sortingOrder = 9200;
                // 水滴大小：舊的小白點是 4px × (2~3.5) ＝ 8~14px 見方，新的水滴圖示要縮到差不多大。
                float size = 8f + Random.value * 6f;
                var drop = GameArt.Item("水滴");     // 8-bit 水滴（GameArt.UsePixelItems）；沒有就退回小白點
                if (drop != null)
                {
                    sr.sprite = drop;
                    // ⚠️ 96×96 的圖裡水滴本身只佔約 17/24 高（四周留透明邊）→ 用內容高度換算，
                    //    直接拿 2~3.5 倍去乘 96px 的圖會變成兩三百 px 的大水球。
                    //    圖本身已經是藍色、不再乘藍色（乘了會變暗變髒），只留一點透明。
                    sr.color = new Color32(255, 255, 255, 230);
                    go.transform.localScale = Vector3.one * (size / (drop.rect.height * DropContentFrac));
                }
                else
                {
                    sr.sprite = Dot();
                    sr.color = new Color32(150, 210, 255, 230);
                    go.transform.localScale = Vector3.one * (size / 4f);
                }

                // 往花圃落下
                go.AddComponent<FloatAway>().Begin(
                    new Vector3(-fromDx * 0.6f, -fromDy * 0.6f - 18f, 0f),
                    0.35f + Random.value * 0.15f, 0.4f);
            }
        }

        /// <summary>items8/water-drop.png 裡水滴（含外框）佔整張圖高的比例（tools/gen_item_art.py 的 draw_water_drop）。</summary>
        const float DropContentFrac = 17f / 24f;

        static Sprite dot;

        /// <summary>水滴用的小白點（程式生成）。</summary>
        static Sprite Dot()
        {
            if (dot != null) return dot;
            var tex = new Texture2D(4, 4, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear };
            for (int y = 0; y < 4; y++)
                for (int x = 0; x < 4; x++)
                    tex.SetPixel(x, y, Color.white);
            tex.Apply();
            dot = Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 1f);
            return dot;
        }
    }
}
