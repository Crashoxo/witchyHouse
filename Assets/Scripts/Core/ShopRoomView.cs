using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 把店裡的東西畫出來：地板底圖 ＋ RoomLayout 裡擺出來的家具 ＋ 擺出來的裝飾。
    ///
    /// 由 PlayerController 進 shop 場景時呼叫 Ensure() —— 不用改場景檔。
    ///
    /// ── 移植註記 ──────────────────────────────────────────────
    /// 對應 Cocos 的 DecorRoom.ts（636 行）的**渲染那一半**：
    ///   applyRoomArt / spawnAll / createEntry / syncAll
    ///
    /// 另一半是「佈置模式」（拖曳家具、格線提示、托盤），拆到 ShopRoomEditor.cs ——
    /// 渲染和編輯是兩件事，原版擠在同一個 636 行的檔裡不好找。
    ///
    /// ⚠️ 家具圖的錨點約定是「圖的正下方中央＝佔地前角」，所以跟 VillagerAnim 一樣，
    ///    SpriteRenderer 掛在子物件上往上推半個身高，父物件的 position 才是落地點。
    /// </summary>
    public class ShopRoomView : MonoBehaviour
    {
        public static ShopRoomView Instance { get; private set; }

        public static ShopRoomView Ensure()
        {
            if (Instance != null) return Instance;
            var go = new GameObject("ShopRoom");
            return go.AddComponent<ShopRoomView>();
        }

        readonly List<GameObject> spawned = new();

        /// <summary>擺出來的家具：物件 ↔ 存檔裡那一筆。佈置模式要靠它才知道拖的是誰。</summary>
        public readonly List<(GameObject Go, PlacedFurniture Data)> Furnitures = new();
        /// <summary>擺出來的裝飾：物件 ↔ 在 DecorCatalog.PlacedList() 裡的索引。</summary>
        public readonly List<(GameObject Go, int Index)> Decors = new();

        void Awake()
        {
            Instance = this;
            GameArt.Preload();
            GameArt.OnReady(() =>
            {
                // 舊存檔裡可能有「已經卡在牆裡」的家具（擺放規則是放的時候才檢查的，
                // 規則改嚴之前存下來的不會自己變好）。要等美術載好才量得出圖的範圍。
                int moved = RoomLayout.RepairPlacements();
                if (moved > 0)
                    UI.Toast.Show($"有 {moved} 件家具卡在牆裡，已經幫你挪回地板上");
                Rebuild();
            });
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>整間店重畫一次（買了新家具、佈置完成後叫這個）。</summary>
        public void Rebuild()
        {
            foreach (var go in spawned) if (go != null) Destroy(go);
            spawned.Clear();
            Furnitures.Clear();
            Decors.Clear();

            ApplyRoomArt();
            SpawnFurniture();
            SpawnDecor();
        }

        /// <summary>地板底圖。整張畫好的 960×640，不是一塊塊磚拼的。</summary>
        void ApplyRoomArt()
        {
            var sp = GameArt.ShopRoom;
            if (sp == null) { Debug.LogWarning("[ShopRoomView] 沒有店內底圖 rooms/shop-room"); return; }
            var go = new GameObject("RoomArt");
            go.transform.SetParent(transform);
            go.transform.position = Vector3.zero;
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = -10000;
            spawned.Add(go);
        }

        void SpawnFurniture()
        {
            foreach (var p in RoomLayout.PlacedList())
            {
                var d = Furniture.ById(p.id);
                if (d == null) continue;
                var sp = GameArt.FurnitureArt(d.Id);
                if (sp == null) { Debug.LogWarning($"[ShopRoomView] 沒有家具圖 furniture/{d.Id}"); continue; }

                // 落地點依基準角＋轉向後的佔地算（見 PlacedFurniture.Size / FurnitureAnchor）
                var front = RoomLayout.AnchorPos(p);
                var go = MakeGrounded($"furn-{d.Id}", sp, front, 1f, p.flip);
                spawned.Add(go);
                Furnitures.Add((go, p));
            }
        }

        /// <summary>擺出來的裝飾品。</summary>
        void SpawnDecor()
        {
            var list = DecorCatalog.PlacedList();
            for (int i = 0; i < list.Count; i++)
            {
                var placed = list[i];
                var d = Decor.ById(placed.id);
                if (d == null) continue;
                var sp = GameArt.Decoration(d.Id);
                if (sp == null) continue;

                // Scale 0 ＝ 沿用預設縮放（最早那批是從大張圖切下來的，不縮會比房間還大）
                float scale = d.Scale > 0f ? d.Scale : DecorCatalog.DefaultScale;
                // ⚠️ 裝飾用的是自由座標 (x, y)，不吃家具那套格盤 —— 它們可以擺在桌上、架上
                var dgo = MakeGrounded($"decor-{d.Id}", sp,
                                       new Vector2(placed.x, placed.y), scale, placed.flip);
                spawned.Add(dgo);
                Decors.Add((dgo, i));
            }
        }

        /// <summary>
        /// 生一個「腳底站在 pos」的圖。
        /// SpriteRenderer 掛在子物件上往上推半身高，所以父物件的 position 就是落地點，
        /// YSort 用它算才正確。
        /// </summary>
        static GameObject MakeGrounded(string name, Sprite sp, Vector2 pos, float scale, bool flip)
        {
            var go = new GameObject(name);
            go.transform.position = new Vector3(pos.x, pos.y, 0f);

            var art = new GameObject("art");
            art.transform.SetParent(go.transform, false);
            art.transform.localScale = new Vector3(flip ? -scale : scale, scale, 1f);
            art.transform.localPosition = new Vector3(0f, sp.rect.height * 0.5f * scale, 0f);

            var sr = art.AddComponent<SpriteRenderer>();
            sr.sprite = sp;
            sr.sortingOrder = Mathf.RoundToInt(-pos.y);
            return go;
        }

        // 佈置模式（拖曳家具、格線提示、托盤）在 ShopRoomEditor.cs。
    }
}
