using UnityEngine;
using UnityEngine.SceneManagement;

namespace WitchShop.Core
{
    /// <summary>
    /// 門/入口：玩家**走上去就會換場景**（也還能按 E）。
    ///
    /// 為什麼是走上去而不是按 E：地圖邊界的傳送點本來就是走過去就換場景，門卻要按 E，
    /// 同樣是發光的傳送點卻兩套規則反而最難懂。按鍵分工是
    /// **E ＝跟東西互動（櫃台/鍋爐/NPC/採集），走上去＝換地方**。
    ///
    /// 兩個距離是分開的：
    ///   interactRange ── 顯示浮動提示（大範圍，遠遠就看得到這裡是門）、也是按 E 的範圍
    ///   autoRange     ── 真的把人送過去的範圍（小，跟地上光圈差不多大）
    /// ⚠️ 分開是必要的：提示範圍 140~200px，若拿它當自動觸發，在城鎮走過小屋旁邊
    ///    就會被吸進店裡。
    /// </summary>
    public class SceneDoor : MonoBehaviour
    {
        [Tooltip("要進入的場景名稱，例：shop")] public string targetScene = "";
        [Tooltip("提示文字")] public string hintText = "按 E 進入";
        [Tooltip("玩家離多近才顯示提示 / 才能按 E（像素）")] public float interactRange = 200f;
        [Tooltip("走上去就自動換場景（關掉就變回只能按 E）")] public bool autoEnter = true;
        [Tooltip("走多近會自動換場景（像素）")] public float autoRange = 70f;

        /// <summary>
        /// 門口相對物件原點的位移。整棟房子當一個物件時，原點是**圖片中心**（城鎮的物件
        /// position 都是圖片中心），而門通常不在正中央（小屋的拱門偏左下）—— 沒有這個位移的話，
        /// 玩家得走到房子中央才進得去。填「門口在圖上的位置 − 圖片中心」；建築門口請放在
        /// 落地範圍（ArtFootprints）底緣外面，玩家從正面走得到，Obstacles 就不會在牆上挖通道。
        /// </summary>
        public float doorX = 0f;
        public float doorY = 0f;

        Transform player;
        GameObject hint;
        bool inRange;
        bool switching;

        /// <summary>
        /// 自動觸發是否已「解鎖」。
        ///
        /// ⚠️ 從別的場景走進來時，玩家的出生點可能就落在門的觸發範圍內，那樣一載入
        ///    就會立刻被彈回去、**兩個場景無限來回**。所以出生時若已站在範圍內就先鎖住，
        ///    等玩家自己走出去一次才啟用。按 E 也要看它 —— 只鎖自動觸發的話，玩家一進
        ///    場景按 E 想做別的事就會被門送回上一個場景。
        /// </summary>
        bool armed = true;

        Vector2 DoorPos => new(transform.position.x + doorX, transform.position.y + doorY);

        float ArmThreshold => Mathf.Max(interactRange, autoRange) + 10f;

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            armed = DistToPlayer() > ArmThreshold;
            BuildHint();
        }

        float DistToPlayer() =>
            player == null ? float.MaxValue : Vector2.Distance(player.position, DoorPos);

        void Update()
        {
            if (player == null || switching) return;

            float dist = DistToPlayer();
            inRange = dist <= interactRange;

            // 解鎖判定要在 autoEnter 之外做 —— 關掉自動過圖的門也要能解鎖，
            // 否則它會永遠停在上鎖狀態，連按 E 都進不去。
            if (!armed && dist > ArmThreshold) armed = true;

            if (hint != null) hint.SetActive(inRange && armed && !UIState.ModalOpen);

            if (UIState.ModalOpen) return;

            if (Input.GetKeyDown(KeyCode.E) && inRange && armed) { Enter(); return; }
            if (autoEnter && armed && dist <= autoRange) Enter();
        }

        void Enter()
        {
            if (switching || string.IsNullOrEmpty(targetScene)) return;

            // ⚠️ 移植途中有些場景還沒蓋（藥水室、後花園），走上去要安靜地當作牆，
            //    而不是把遊戲炸掉。
            if (!Application.CanStreamedLevelBeLoaded(targetScene))
            {
                Debug.Log($"[SceneDoor] 場景「{targetScene}」還沒搬過來，這道門先當牆");
                return;
            }

            switching = true;
            UI.SceneFade.Go(targetScene);       // 淡出 → 切場景 → 淡入
        }

        /// <summary>門口上方的浮動提示。</summary>
        void BuildHint()
        {
            hint = new GameObject("hint");
            hint.transform.SetParent(transform, false);
            hint.transform.localPosition = new Vector3(doorX, doorY + 70f, 0f);

            var tm = hint.AddComponent<TextMesh>();
            tm.text = hintText;
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = new Color32(255, 244, 214, 255);

            var font = UI.CjkFont.Get();
            if (font != null)
            {
                tm.font = font;
                hint.GetComponent<MeshRenderer>().material = font.material;
            }
            hint.GetComponent<MeshRenderer>().sortingOrder = 9400;
            hint.SetActive(false);
        }
    }
}
