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
        GameObject thirsty;      // 「缺水」提醒（新版：一顆輕輕上下晃的水滴；InteractHint 開關關掉時是舊的「缺水」兩個字）
        /// <summary>這塊花圃的互動（GardenRoom 生的）—— 它正在冒提示時，缺水的水滴先收起來，兩個不疊在一起。</summary>
        public Interactable interactable;

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
            // 從磚面中心長出來（新圖入土點＝花圃中心；舊圖同原版的 -6，見 GardenData.PlantBottomY）
            plantGo.transform.localPosition = new Vector3(0f, GardenData.PlantBottomY, 0f);
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
                    new Vector3(0f, GardenData.PlantBottomY + f.rect.height * 0.5f * GardenData.FlowerScale, 0f);
            }

            if (thirsty != null) thirsty.SetActive(ShowThirsty());
        }

        bool ShowThirsty() => Garden.NeedsWater(index) && (interactable == null || Interact.Shown != interactable);

        void LateUpdate()
        {
            if (thirsty == null) return;
            bool on = ShowThirsty();
            if (thirsty.activeSelf != on) thirsty.SetActive(on);
        }

        /// <summary>互動提示的底邊：土＋花的最上緣（不算缺水水滴）往上一點。</summary>
        public Vector3 HintAnchor()
        {
            float top = soil != null && soil.sprite != null ? soil.bounds.max.y : transform.position.y + 20f;
            if (plant != null && plant.gameObject.activeSelf && plant.sprite != null) top = Mathf.Max(top, plant.bounds.max.y);
            return new Vector3(transform.position.x, top + 4f, 0f);
        }

        // ──────────── 佈置模式（8-bit 後花園：花圃可以搬，見 GardenArrange）────────────

        /// <summary>拖著走時的排序：蓋過別的花圃、前景牆（GardenRoomData.FrontOrder 3000）與格線預覽，提示字（9300 起）之下。</summary>
        const int LiftOrder = 5000;
        bool lifted;
        Color soilCol0 = Color.white, plantCol0 = Color.white;

        /// <summary>
        /// 搬到別格（佈置模式放下時）：整塊（土、花、缺水提醒、之後的飄字）跟著物件走，
        /// 排序照新位置重算（跟 Init 同一條規則）。花長到哪、澆過水沒都在 Garden 的資料裡，不受影響。
        /// </summary>
        public void MoveTo(Vector2 pos)
        {
            transform.position = new Vector3(pos.x, pos.y, 0f);
            if (!lifted) ApplyOrder(pos.y);
        }

        /// <summary>拖曳中：整塊浮到最上層並乘上 tint（綠＝放得下、紅＝不行）；on=false ＝ 放下：顏色還原、排序照目前位置。</summary>
        public void SetLifted(bool on, Color tint = default)
        {
            if (soil == null || plant == null) return;
            if (on)
            {
                if (!lifted) { soilCol0 = soil.color; plantCol0 = plant.color; lifted = true; }
                soil.color = soilCol0 * tint;
                plant.color = plantCol0 * tint;
                soil.sortingOrder = LiftOrder - 1;
                plant.sortingOrder = LiftOrder;
                return;
            }
            if (lifted) { soil.color = soilCol0; plant.color = plantCol0; }
            lifted = false;
            ApplyOrder(transform.position.y);
        }

        /// <summary>⚠️ 跟 Init 裡設的排序是同一條規則（土在花下面一層）；改 Init 的話這裡一起改。</summary>
        void ApplyOrder(float y)
        {
            soil.sortingOrder = Mathf.RoundToInt(-y) - 1;
            plant.sortingOrder = Mathf.RoundToInt(-y);
        }

        void BuildThirsty()
        {
            if (InteractHint.Enabled)
            {
                // 「缺水」兩個字 → 一顆水滴（要高過盛開的花頂，同舊字的高度）
                var drop = StatusBubble.Create(transform, new Vector3(0f, GardenData.ThirstyLabelY, 0f),
                                               HintIcons.Items8("water-drop"), 24f, 9300);
                thirsty = drop.gameObject;
                thirsty.SetActive(false);
                return;
            }

            thirsty = new GameObject("thirsty");
            thirsty.transform.SetParent(transform, false);
            thirsty.transform.localPosition = new Vector3(0f, GardenData.ThirstyLabelY, 0f);   // 要高過盛開的花頂

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

        /// <summary>操作後在花圃上方冒的小圖（[圖][小圖][×N]）；開關關掉時退回舊的一行字 legacy。</summary>
        public void PopIcon(Sprite icon, string count, Sprite icon2, string legacy)
        {
            IconPopup.Show(transform.position + new Vector3(0f, 30f, 0f), icon, count, icon2, legacy);
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
