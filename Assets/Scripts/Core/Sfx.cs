using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;

namespace WitchShop.Core
{
    /// <summary>
    /// 音效：任何地方一行 <c>Sfx.Play("coin")</c> 就響，不用先準備什麼。
    ///
    /// 音檔放在 <c>Resources/audio/&lt;名字&gt;.wav</c>，照檔名載入、載過就快取。
    /// 現在那批是 <c>tools/gen_sfx.py</c> 合成的 8-bit 佔位音；有正式音檔時
    /// **用同名檔蓋掉就好**，程式不用改。
    ///
    /// 功能：
    ///   ● 變體輪播 —— <c>Play("step")</c> 會在 step-1..3 之間隨機挑（不連續重複同一個）。
    ///   ● 最短重播間隔 —— 同一個音效在間隔內再叫一次會被丟掉，
    ///     免得同一幀觸發十次疊成一聲爆音（例如一次搬一整排東西）。
    ///   ● 小幅隨機 pitch —— 腳步、對話 blip 這種一直重複的聲音才不會像機關槍。
    ///   ● 總音量與靜音存進存檔（<see cref="Volume"/> / <see cref="Muted"/>），
    ///     之後的設定介面直接接這兩個屬性。<c>M</c> 鍵切換靜音。
    ///   ● UI 按鈕的 click 音：面板建好時呼叫一次 <see cref="BindClicks"/>，
    ///     不用逐顆按鈕貼（見那支的說明）。
    ///
    /// ⚠️ 找不到檔案時**靜默略過**（同一個名字只警告一次），絕不丟例外 ——
    ///    音效壞掉不該讓遊戲跟著壞。
    ///
    /// ⚠️ **場景裡沒有 AudioListener**（場景是 Editor 產生器用 AddComponent&lt;Camera&gt;() 建的，
    ///    不會順便帶 Listener）。所以這個常駐物件自己掛一個；
    ///    哪天場景裡有了別的 Listener，換場時會自動把自己這個關掉（兩個同時開 Unity 會一直警告）。
    ///
    /// ⚠️ 不受 <c>Time.timeScale</c> 影響：AudioSource 本來就不吃 timeScale，
    ///    重播間隔也是用 <c>Time.unscaledTime</c> 量的。
    ///
    /// ⚠️ 網頁版（WebGL）沒有執行緒、也不能即時合成（OnAudioFilterRead），所以一律播預先產好的 .wav。
    ///    瀏覽器要等玩家第一次點擊／按鍵之後才准出聲，開場那幾聲（例如公告板）聽不到是正常的。
    /// </summary>
    public class Sfx : MonoBehaviour
    {
        /// <summary>音檔在 Resources 底下的資料夾（小寫，見 PortNotes）。</summary>
        const string Folder = "audio/";
        /// <summary>同時最多幾個聲音（不夠時搶最舊的那個）。</summary>
        const int PoolSize = 10;
        /// <summary>存檔 key（刻意不列進 SaveManager.SaveKeys，理由見那邊的註解）。</summary>
        const string SaveKey = "witch.audio";
        const float DefaultVolume = 0.8f;
        /// <summary>沒特別指定時，同一個音效的最短重播間隔（秒）。</summary>
        const float DefaultGap = 0.05f;

        /// <summary>有幾個變體：Play("step") → step-1 / step-2 / step-3。</summary>
        static readonly Dictionary<string, int> Variants = new() { ["step"] = 3 };

        /// <summary>個別的最短重播間隔（秒）。</summary>
        static readonly Dictionary<string, float> Gaps = new()
        {
            ["step"] = 0.09f, ["talk"] = 0.07f, ["coin"] = 0.09f,
            ["ui-click"] = 0.03f, ["spell-hit"] = 0.08f, ["deny"] = 0.12f,
        };

        /// <summary>呼叫端沒指定 pitchJitter 時用的預設隨機幅度（±比例）。</summary>
        static readonly Dictionary<string, float> Jitters = new()
        {
            ["step"] = 0.08f, ["talk"] = 0.12f, ["gather"] = 0.06f, ["pickup"] = 0.04f,
            ["coin"] = 0.03f, ["spell-hit"] = 0.08f, ["place"] = 0.06f, ["water"] = 0.05f,
            ["ui-click"] = 0.03f, ["cast"] = 0.03f,
        };

        static Sfx instance;
        static readonly Dictionary<string, AudioClip> clips = new();
        static readonly HashSet<string> missing = new();
        static readonly Dictionary<string, float> lastAt = new();
        static readonly Dictionary<string, int> lastVariant = new();

        /// <summary>最近一次「有意義的聲音」是哪一幀（腳步與 click 本身不算）。給延後的 click 判斷用。</summary>
        static int lastCueFrame = -1;
        /// <summary>有一個 UI click 等著下一幀決定要不要響（-1＝沒有）。</summary>
        static int pendingClickFrame = -1;

        // ──────────── 設定（音量／靜音）────────────

        [Serializable]
        class Settings
        {
            public float volume = DefaultVolume;
            public bool muted;
        }

        static Settings settings;

        static Settings Prefs
        {
            get
            {
                if (settings != null) return settings;
                settings = new Settings();
                try
                {
                    var raw = SaveManager.GetString(SaveKey);
                    if (!string.IsNullOrEmpty(raw)) JsonUtility.FromJsonOverwrite(raw, settings);
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[Sfx] 音量設定讀不懂，用預設值：{e.Message}");
                    settings = new Settings();
                }
                settings.volume = Mathf.Clamp01(settings.volume);
                return settings;
            }
        }

        static void SavePrefs() => SaveManager.SetString(SaveKey, JsonUtility.ToJson(Prefs));

        /// <summary>總音量 0..1（存檔）。給之後的設定介面用。</summary>
        public static float Volume
        {
            get => Prefs.volume;
            set { Prefs.volume = Mathf.Clamp01(value); SavePrefs(); }
        }

        /// <summary>靜音（存檔）。靜音時 Play 直接略過。</summary>
        public static bool Muted
        {
            get => Prefs.muted;
            set
            {
                Prefs.muted = value;
                SavePrefs();
                if (value && instance != null) instance.StopAll();   // 正在響的長音（旋律）也一起收掉
            }
        }

        /// <summary>切換靜音並冒一則提示（M 鍵）。</summary>
        public static void ToggleMute()
        {
            Muted = !Muted;
            UI.Toast.Show(Muted ? "音效：靜音（M 切換）" : "音效：開啟（M 切換）");
            if (!Muted) Play("ui-click");
        }

        // ──────────── 對外：播放 ────────────

        /// <summary>
        /// 播一個音效。找不到檔案、靜音、或還在重播間隔內就什麼都不做。
        /// </summary>
        /// <param name="name">檔名（不含副檔名）。有變體的直接給基底名，例如 "step"。</param>
        /// <param name="volume">這一次的音量倍率（再乘總音量）。</param>
        /// <param name="pitchJitter">隨機 pitch 幅度（±比例，0.1＝±10%）；負數＝用該音效的預設值。</param>
        public static void Play(string name, float volume = 1f, float pitchJitter = -1f)
        {
            if (string.IsNullOrEmpty(name)) return;
            try { PlayCore(name, volume, pitchJitter); }
            catch (Exception e)
            {
                // 音效壞掉不能讓呼叫端跟著炸（呼叫端多半在遊戲邏輯的正中間）
                if (missing.Add("!" + name)) Debug.LogWarning($"[Sfx] 播「{name}」失敗：{e.Message}");
            }
        }

        static void PlayCore(string name, float volume, float pitchJitter)
        {
            if (Muted) return;
            var self = Ensure();
            if (self == null) return;

            // 同一個音效的最短重播間隔（用 unscaledTime：暫停、慢動作都不影響）
            float now = Time.unscaledTime;
            float gap = Gaps.TryGetValue(name, out var g) ? g : DefaultGap;
            if (lastAt.TryGetValue(name, out var t) && now - t < gap) return;

            var clip = Clip(PickFile(name));
            if (clip == null) return;
            lastAt[name] = now;

            if (name != "step" && name != "ui-click") lastCueFrame = Time.frameCount;

            float j = pitchJitter >= 0f ? pitchJitter : (Jitters.TryGetValue(name, out var dj) ? dj : 0f);
            float pitch = 1f + (j > 0f ? UnityEngine.Random.Range(-j, j) : 0f);
            self.Emit(clip, Mathf.Clamp01(volume) * Volume, pitch);
        }

        /// <summary>有變體的音效：隨機挑一個，但不跟上一次一樣。</summary>
        static string PickFile(string name)
        {
            if (!Variants.TryGetValue(name, out int n) || n <= 1) return name;
            int prev = lastVariant.TryGetValue(name, out var p) ? p : -1;
            int i = UnityEngine.Random.Range(0, n);
            if (i == prev) i = (i + 1 + UnityEngine.Random.Range(0, n - 1)) % n;
            lastVariant[name] = i;
            return $"{name}-{i + 1}";
        }

        static AudioClip Clip(string file)
        {
            if (clips.TryGetValue(file, out var c) && c != null) return c;
            if (missing.Contains(file)) return null;

            c = Resources.Load<AudioClip>(Folder + file);
            if (c == null)
            {
                missing.Add(file);       // 只警告一次，之後靜默略過
                Debug.LogWarning($"[Sfx] 找不到音效 Resources/{Folder}{file}（之後不再提醒）—— " +
                                 "跑一次 python tools/gen_sfx.py 產生佔位音");
                return null;
            }
            clips[file] = c;
            return c;
        }

        // ──────────── 對外：UI 按鈕的共用 click 音 ────────────

        /// <summary>
        /// 讓這棵 UI 樹裡**所有按鈕**被點時響一聲 ui-click。面板 Build 時呼叫一次就好。
        ///
        /// 做法是在根節點註冊 ClickEvent（按鈕的點擊會冒泡上來），不用逐顆按鈕貼。
        ///
        /// ⚠️ click 音**延到下一幀才決定要不要響**：同一幀裡如果已經有更具體的音效
        ///    （關閉面板的 ui-close、買東西的 buy、錢不夠的 deny、切分頁的 ui-tab…），
        ///    就不再疊一聲 click。按鈕自己的 clicked 回呼與冒泡上來的 ClickEvent
        ///    誰先誰後不用管 —— 反正都在同一幀。
        /// </summary>
        public static void BindClicks(VisualElement root)
        {
            if (root == null) return;
            root.RegisterCallback<ClickEvent>(e =>
            {
                for (var el = e.target as VisualElement; el != null && el != root; el = el.parent)
                {
                    if (el is Button b)
                    {
                        if (b.enabledInHierarchy) pendingClickFrame = Time.frameCount;
                        return;
                    }
                }
            });
        }

        // ──────────── 常駐物件 ────────────

        /// <summary>遊戲一開就把常駐物件生出來（M 鍵要從第一個場景就能用）。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        /// <summary>關掉 Domain Reload 進 Play 時，靜態欄位會留著上一輪的東西 —— 這裡清乾淨。</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            instance = null;
            settings = null;
            clips.Clear(); missing.Clear(); lastAt.Clear(); lastVariant.Clear();
            lastCueFrame = -1; pendingClickFrame = -1;
        }

        static Sfx Ensure()
        {
            if (instance != null) return instance;
            var go = new GameObject("Sfx");
            DontDestroyOnLoad(go);
            return go.AddComponent<Sfx>();      // Awake 會設 instance
        }

        AudioSource[] pool;
        int cursor;
        AudioListener listener;

        void Awake()
        {
            instance = this;
            pool = new AudioSource[PoolSize];
            for (int i = 0; i < PoolSize; i++)
            {
                var s = gameObject.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0f;             // 純 2D：位置不影響音量
                s.ignoreListenerPause = true;    // 之後若用 AudioListener.pause 做暫停選單，UI 音仍要響
                pool[i] = s;
            }
            listener = gameObject.AddComponent<AudioListener>();
            SyncListener();
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        void OnDestroy()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            if (instance == this) instance = null;
        }

        void OnSceneLoaded(Scene s, LoadSceneMode m) => SyncListener();

        /// <summary>場景裡已經有別的 Listener 就把自己的關掉（兩個同時開，Unity 會每幀警告）。</summary>
        void SyncListener()
        {
            if (listener == null) return;
            bool other = false;
            foreach (var l in FindObjectsByType<AudioListener>(FindObjectsInactive.Exclude))
                if (l != listener && l.enabled) { other = true; break; }
            listener.enabled = !other;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.M)) ToggleMute();

            // 延後的 click：同一幀已經有更具體的音效就不響（見 BindClicks）
            if (pendingClickFrame >= 0 && Time.frameCount > pendingClickFrame)
            {
                bool covered = lastCueFrame == pendingClickFrame;
                pendingClickFrame = -1;
                if (!covered) Play("ui-click");
            }
        }

        /// <summary>挑一個空著的 AudioSource 播；全在響就搶最舊的那個（輪著搶）。</summary>
        void Emit(AudioClip clip, float volume, float pitch)
        {
            AudioSource src = null;
            for (int i = 0; i < pool.Length; i++)
            {
                var s = pool[(cursor + i) % pool.Length];
                if (!s.isPlaying) { src = s; break; }
            }
            if (src == null) src = pool[cursor];
            cursor = (cursor + 1) % pool.Length;

            src.clip = clip;
            src.volume = volume;
            src.pitch = pitch;
            src.Play();
        }

        void StopAll()
        {
            if (pool == null) return;
            foreach (var s in pool) if (s != null) s.Stop();
        }
    }
}
