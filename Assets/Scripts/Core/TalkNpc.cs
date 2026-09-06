using System;
using System.Collections.Generic;
using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 村民友誼度：每天第一次跟同一位村民交談加分，滿一定點數升一顆心。
    /// 用名字當 key（同 QuestLog 的 Giver 對應方式），新增村民只要掛上 TalkNpc 就好。
    /// </summary>
    public static class Friendship
    {
        const string Key = "witch.friendship";

        [Serializable] class Shape
        {
            public List<string> names = new();
            public List<int> points = new();
            public List<int> lastTalkDay = new();   // 上次交談是第幾天（避免同一天重複給）
        }

        static Shape data;

        static Shape Data
        {
            get
            {
                if (data == null)
                {
                    try { data = JsonUtility.FromJson<Shape>(SaveManager.GetString(Key)); }
                    catch { data = null; }
                    data ??= new Shape();
                }
                return data;
            }
        }

        static void Save() => SaveManager.SetString(Key, JsonUtility.ToJson(Data));

        static int IndexOf(string name)
        {
            int i = Data.names.IndexOf(name);
            if (i >= 0) return i;
            Data.names.Add(name); Data.points.Add(0); Data.lastTalkDay.Add(0);
            return Data.names.Count - 1;
        }

        public static int PointsOf(string name) => Data.points[IndexOf(name)];

        /// <summary>幾顆心（0..MaxHearts）。</summary>
        public static int Hearts(string name) =>
            Mathf.Min(Villagers.MaxHearts, PointsOf(name) / Villagers.PointsPerHeart);

        /// <summary>交談。每天第一次才加分；回傳這次加了多少。</summary>
        public static int Talk(string name)
        {
            int i = IndexOf(name);
            int today = TimeSystem.TotalDay;
            if (Data.lastTalkDay[i] == today) return 0;      // 同一天聊過了
            Data.lastTalkDay[i] = today;
            Data.points[i] += Villagers.TalkPoints;
            Save();
            return Villagers.TalkPoints;
        }
    }

    /// <summary>
    /// 可以交談的 NPC：走近按 E 開對話。
    ///
    /// ⚠️ NpcName 必須跟 Data.Quests 裡的 Giver、以及 Data.Villagers 的 Name 完全一致 ——
    ///    任務與友誼度都是用名字當 key 對應的。
    ///
    /// 有任務可談就走任務對話（提供／進度／回報），沒有就走一般閒聊。
    /// </summary>
    public class TalkNpc : MonoBehaviour
    {
        [Tooltip("NPC 名字（＝任務的 Giver、友誼度的 key）")]
        public string npcName = "村民";
        [Tooltip("頭像檔名（Resources/portraits 底下；留空＝不顯示頭像）")]
        public string portrait = "";
        [Tooltip("沒有任務時說的閒聊（留空＝用 Data.Dialogue 的預設）")]
        public string[] lines = new string[0];
        [Tooltip("玩家離多近才能交談（像素）")]
        public float interactRange = 200f;

        /// <summary>
        /// 有填就代表這位 NPC 兼賣東西：閒聊的最後一句會多一個「看看貨」的選項。
        ///
        /// ⚠️ 刻意做成「對話裡的選項」而不是另一個按 E 的觸發點 —— 兩個感應圈重疊時，
        ///    Unity 沒有保證元件的 Update 順序，同一顆 E 會**隨機**觸發其中一個。
        ///    原專案的註解也反覆警告過這件事（花園的門踩過）。
        /// </summary>
        public string shopTitle = "";

        Transform player;
        GameObject hint;
        bool inRange;

        void Start()
        {
            var p = GameObject.Find("Player");
            player = p != null ? p.transform : null;
            BuildHint();
        }

        void Update()
        {
            if (player == null) return;
            inRange = Vector2.Distance(player.position, transform.position) <= interactRange;

            if (hint != null)
            {
                bool show = inRange && !UIState.ModalOpen;
                hint.SetActive(show);
                if (show) UpdateHintText();
            }

            if (inRange && !UIState.ModalOpen && Input.GetKeyDown(KeyCode.E)) Talk();
        }

        void Talk()
        {
            Friendship.Talk(npcName);      // 每天第一次交談加友誼

            // 名字對得上任務 Giver、而且此刻有任務可談 → 走任務對話；否則一般閒聊
            string qid = QuestLog.CurrentFor(npcName);
            if (qid != null) { OpenQuest(qid); return; }

            var chat = lines != null && lines.Length > 0 ? lines : Dialogue.DefaultNpcLines;
            var script = UI.DialogueLine.Of(chat);

            // 兼賣東西的 NPC：聊完問一句要不要看貨
            if (!string.IsNullOrEmpty(shopTitle))
            {
                string title = shopTitle;
                script.Add(new UI.DialogueLine($"要看看{title}的貨嗎？", new List<(string, Action)>
                {
                    ("看看貨", () => UI.GoodsShopPanel.Ensure().Open(title)),
                    ("不用了", null),
                }));
            }

            UI.Dialogue.Ensure().Open(npcName, script, portrait);
        }

        /// <summary>依任務狀態開對應對話：可接→提供＋接受/拒絕；進行中→提醒；可回報→領獎。</summary>
        void OpenQuest(string qid)
        {
            var d = QuestLog.Def(qid);
            var st = QuestLog.StatusOf(qid);
            string who = npcName, face = portrait;

            switch (st)
            {
                case QuestStatus.Available:
                {
                    var script = UI.DialogueLine.Of(d.OfferLines);
                    script.Add(new UI.DialogueLine(
                        $"任務：{d.Title}（{QuestLog.ObjectiveText(d)}）\n獎勵：{QuestLog.RewardText(d)}"));
                    script.Add(new UI.DialogueLine("要接下這個任務嗎？", new List<(string, Action)>
                    {
                        ("接受", () =>
                        {
                            QuestLog.Accept(qid);
                            UI.Dialogue.Ensure().Open(who,
                                new[] { "好，就交給你了！（按 Q 可隨時查看任務）" }, face);
                        }),
                        ("再想想", null),
                    }));
                    UI.Dialogue.Ensure().Open(who, script, face);
                    break;
                }

                case QuestStatus.Active:
                {
                    var script = UI.DialogueLine.Of(d.ActiveLines);
                    script.Add(new UI.DialogueLine($"目前進度：{QuestLog.ProgressText(qid)}"));
                    UI.Dialogue.Ensure().Open(who, script, face);
                    break;
                }

                case QuestStatus.Ready:
                {
                    var script = UI.DialogueLine.Of(d.ReadyLines);
                    script.Add(new UI.DialogueLine("要現在回報領取獎勵嗎？", new List<(string, Action)>
                    {
                        ("回報", () =>
                        {
                            if (!QuestLog.Claim(qid)) return;
                            var done = UI.DialogueLine.Of(d.DoneLines);
                            done.Add(new UI.DialogueLine($"獲得：{QuestLog.RewardText(d)}"));
                            UI.Dialogue.Ensure().Open(who, done, face);
                        }),
                        ("等一下", null),
                    }));
                    UI.Dialogue.Ensure().Open(who, script, face);
                    break;
                }
            }
        }

        // ──────────── 頭上的提示 ────────────

        void BuildHint()
        {
            hint = new GameObject("hint");
            hint.transform.SetParent(transform, false);
            hint.transform.localPosition = new Vector3(0f, 96f, 0f);

            var tm = hint.AddComponent<TextMesh>();
            tm.fontSize = 36;
            tm.characterSize = 4.5f;
            tm.anchor = TextAnchor.MiddleCenter;
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

        /// <summary>可回報的任務要標出來，玩家才知道該回去找誰。</summary>
        void UpdateHintText()
        {
            string qid = QuestLog.CurrentFor(npcName);
            bool ready = qid != null && QuestLog.StatusOf(qid) == QuestStatus.Ready;
            bool offer = qid != null && QuestLog.StatusOf(qid) == QuestStatus.Available;
            var tm = hint.GetComponent<TextMesh>();
            tm.text = ready ? $"！按 E 回報　{npcName}"
                    : offer ? $"？按 E 交談　{npcName}"
                    : $"按 E 交談　{npcName}";
            tm.color = ready ? new Color32(255, 226, 120, 255)
                     : offer ? new Color32(190, 240, 190, 255)
                     : new Color32(255, 244, 214, 255);
        }
    }
}
