using UnityEditor;
using UnityEngine;

/// <summary>
/// 背景音樂的匯入設定：路徑含 <c>Resources/audio/bgm/</c> 的音檔，匯入當下就改成
/// Vorbis（品質約 0.5）、CompressedInMemory、強制單聲道。
///
/// 為什麼要特別設：<c>tools/gen_bgm.py</c> 產的是未壓縮的 16-bit wav，一首就 1.5 MB 上下；
/// 照 Unity 的預設設定匯入，四首加起來會讓網頁版多好幾 MB。壓成 Vorbis 之後每首只剩幾百 KB。
/// CompressedInMemory：記憶體裡放壓縮過的資料、播的時候才解 —— 背景音樂一次只響一兩首，解碼成本很小，
/// 換來記憶體與下載量都小。
///
/// ⚠️ **只碰 bgm 資料夾**：音效（<c>Resources/audio/*.wav</c>）都很短，維持 Unity 的預設設定
///    （解成 PCM 播最快、延遲最低），這裡一律不動。
/// ⚠️ 改了這支的數值要把 <see cref="GetVersion"/> +1，已經匯入過的檔案才會重新匯入；
///    還是沒套上（Inspector 顯示的不是 Vorbis）就對 bgm 資料夾按右鍵 Reimport。
/// </summary>
public class BgmImporter : AssetPostprocessor
{
    const string Folder = "/Resources/audio/bgm/";

    /// <summary>
    /// 改了下面的設定就把版本 +1 —— Unity 會把這支管到的音檔自動重新匯入，不用手動 Reimport。
    /// </summary>
    public override uint GetVersion() => 1;

    void OnPreprocessAudio()
    {
        // Unity 的 assetPath 一律是正斜線（Windows 上也是），所以不需要轉換路徑分隔符號。
        if (assetPath.IndexOf(Folder, System.StringComparison.Ordinal) < 0) return;

        var ai = (AudioImporter)assetImporter;
        ai.forceToMono = true;

        var s = ai.defaultSampleSettings;
        s.loadType = AudioClipLoadType.CompressedInMemory;
        s.compressionFormat = AudioCompressionFormat.Vorbis;
        s.quality = 0.5f;                                   // 0..1；8-bit 風的合成音 0.5 綽綽有餘
        ai.defaultSampleSettings = s;
    }
}
