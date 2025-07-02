
import React, { useState, useEffect, useCallback } from 'react';
import type { ImageRecord, Dimension, Notification, NotificationType } from './types.ts';
import { ART_STYLES, DIMENSIONS } from './constants.tsx';
import { beautifyPrompt, getRandomPrompt } from './services/geminiService.ts';
import { SparklesIcon, TrashIcon, ShuffleIcon } from './components/icons.tsx';
import ImageCard from './components/ImageCard.tsx';
import HistoryItem from './components/HistoryItem.tsx';
import Spinner from './components/Spinner.tsx';
import { NotificationContainer } from './components/Notification.tsx';

const App: React.FC = () => {
  const [prompt, setPrompt] = useState<string>('');
  const [selectedStyle, setSelectedStyle] = useState<string>(ART_STYLES[0].promptSuffix);
  const [dimension, setDimension] = useState<Dimension>(DIMENSIONS[2]);
  const [batchCount, setBatchCount] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isHelperLoading, setIsHelperLoading] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<ImageRecord[]>([]);
  const [history, setHistory] = useState<ImageRecord[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [previewImage, setPreviewImage] = useState<ImageRecord | null>(null);

  useEffect(() => {
    try {
      const storedHistory = localStorage.getItem('imageGenHistory');
      if (storedHistory) {
        setHistory(JSON.parse(storedHistory));
      }
    } catch (error) {
      console.error("Failed to load history from localStorage", error);
      addNotification('無法加載歷史紀錄', 'error');
    }
  }, []);

  const addNotification = (message: string, type: NotificationType) => {
    setNotifications(prev => [...prev, { id: Date.now(), message, type }]);
  };

  const removeNotification = (id: number) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };
  
  const handleDownload = useCallback((image: ImageRecord) => {
    fetch(image.url)
      .then(response => response.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safePrompt = image.prompt.replace(/[^a-z0-9]/gi, '_').slice(0, 30);
        a.download = `pollinations_${safePrompt}.png`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        addNotification('圖像已開始下載', 'success');
      })
      .catch(err => {
        console.error("Download failed:", err);
        addNotification('下載失敗，請稍後再試', 'error');
      });
  }, []);
  
  const generateImages = async () => {
    if (!prompt.trim()) {
      addNotification('請輸入提示詞', 'error');
      return;
    }
    setIsLoading(true);
    setGeneratedImages([]);
    const newImages: ImageRecord[] = [];
    const currentTimestamp = new Date().toISOString();

    const generationPromises = Array.from({ length: batchCount }, (_, i) => {
      const seed = Math.floor(Math.random() * 100000);
      const fullPrompt = encodeURIComponent(`${prompt}${selectedStyle}`);
      const imageUrl = `https://image.pollinations.ai/prompt/${fullPrompt}?width=${dimension.width}&height=${dimension.height}&seed=${seed}&model=flux&nologo=true`;
      
      const newImage: ImageRecord = {
        id: `${currentTimestamp}-${i}`,
        prompt: prompt,
        style: ART_STYLES.find(s => s.promptSuffix === selectedStyle)?.name || '自訂風格',
        url: imageUrl,
        width: dimension.width,
        height: dimension.height,
        timestamp: currentTimestamp,
      };
      newImages.push(newImage);
      
      // We don't need to actually fetch it here, just prepare the record
      return Promise.resolve();
    });

    await Promise.all(generationPromises);
    
    setGeneratedImages(newImages);
    setHistory(prev => {
        const updatedHistory = [...newImages, ...prev].slice(0, 50); // Keep history to 50 items
        try {
            localStorage.setItem('imageGenHistory', JSON.stringify(updatedHistory));
        } catch(error) {
            console.error("Failed to save history to localStorage", error);
            addNotification('無法保存歷史紀錄', 'error');
        }
        return updatedHistory;
    });

    setIsLoading(false);
    addNotification(`已成功生成 ${batchCount} 張圖像`, 'success');
  };
  
  const handleBeautify = async () => {
    if (!prompt.trim()) {
      addNotification('請先輸入提示詞再進行美化', 'error');
      return;
    }
    setIsHelperLoading('beautify');
    try {
      const beautifulPrompt = await beautifyPrompt(prompt);
      setPrompt(beautifulPrompt);
      addNotification('提示詞已美化', 'success');
    } catch (e: any) {
      addNotification(e.message || '美化失敗', 'error');
    } finally {
      setIsHelperLoading(null);
    }
  };

  const handleRandom = async () => {
    setIsHelperLoading('random');
    try {
      const randomPrompt = await getRandomPrompt();
      setPrompt(randomPrompt);
      addNotification('已生成隨機靈感', 'success');
    } catch (e: any) {
      addNotification(e.message || '獲取靈感失敗', 'error');
    } finally {
      setIsHelperLoading(null);
    }
  };
  
  const handleClear = () => {
    setPrompt('');
    addNotification('提示詞已清空', 'success');
  };

  const isApiKeyMissing = !process.env.API_KEY;

  return (
    <>
      <NotificationContainer notifications={notifications} onDismiss={removeNotification} />
      
      {previewImage && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" 
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-3xl max-h-[90vh] p-4" onClick={e => e.stopPropagation()}>
            <img src={previewImage.url} alt={previewImage.prompt} className="object-contain w-full h-full rounded-lg shadow-2xl"/>
            <button 
              onClick={() => setPreviewImage(null)} 
              className="absolute -top-2 -right-2 bg-white text-black rounded-full h-8 w-8 flex items-center justify-center"
            >&times;</button>
          </div>
        </div>
      )}

      <div className="min-h-screen text-white p-4 sm:p-6 lg:p-8 font-sans">
        <main className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Panel: Controls */}
          <div className="lg:col-span-1 space-y-6">
            <header className="p-4 rounded-xl bg-gradient-to-br from-purple-600/50 to-blue-500/50">
              <h1 className="text-3xl font-bold text-center text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-pink-300">AI 圖像生成器</h1>
              <p className="text-center text-purple-200 mt-1">輸入您的創意，見證魔法</p>
            </header>

            <div className="p-6 bg-slate-800/50 backdrop-blur-md rounded-xl space-y-6 ring-1 ring-white/10">
              {/* Prompt Input */}
              <div>
                <label htmlFor="prompt" className="block text-sm font-medium text-purple-300 mb-2">1. 輸入提示詞</label>
                <textarea
                  id="prompt"
                  rows={4}
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  placeholder="例如：一隻戴著太陽眼鏡的貓在月球上開跑車"
                  className="w-full bg-slate-900/70 border border-slate-700 rounded-lg p-3 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition"
                />
                 <div className="flex justify-end space-x-2 mt-2">
                    <button onClick={handleRandom} disabled={!!isHelperLoading || isApiKeyMissing} title={isApiKeyMissing ? "未配置API Key" : "隨機靈感"} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-gradient-to-r from-green-500 to-teal-500 hover:from-green-600 hover:to-teal-600 disabled:opacity-50 transition-transform hover:scale-105">
                      {isHelperLoading === 'random' ? <Spinner/> : <ShuffleIcon className="w-4 h-4"/>} 🎲 隨機靈感
                    </button>
                    <button onClick={handleClear} disabled={!!isHelperLoading} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 disabled:opacity-50 transition-transform hover:scale-105">
                      {isHelperLoading === 'clear' ? <Spinner/> : <TrashIcon className="w-4 h-4"/>} 🗑️ 清空
                    </button>
                    <button onClick={handleBeautify} disabled={!!isHelperLoading || isApiKeyMissing} title={isApiKeyMissing ? "未配置API Key" : "美化描述"} className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-md bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 disabled:opacity-50 transition-transform hover:scale-105">
                      {isHelperLoading === 'beautify' ? <Spinner/> : <SparklesIcon className="w-4 h-4"/>} ✨ 美化描述
                    </button>
                </div>
              </div>
              
              {/* Style Selection */}
              <div>
                <label htmlFor="style" className="block text-sm font-medium text-purple-300 mb-2">2. 選擇藝術風格</label>
                <select id="style" value={selectedStyle} onChange={e => setSelectedStyle(e.target.value)} className="w-full bg-slate-900/70 border border-slate-700 rounded-lg p-3 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition appearance-none bg-no-repeat bg-right pr-8" style={{backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.5rem center', backgroundSize: '1.5em 1.5em'}}>
                  {ART_STYLES.map(style => (
                    <option key={style.name} value={style.promptSuffix}>{style.icon} {style.name}</option>
                  ))}
                </select>
              </div>

              {/* Dimension & Batch */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-purple-300 mb-2">3. 尺寸</label>
                  <div className="grid grid-cols-2 gap-2">
                    {DIMENSIONS.map(d => (
                      <button key={d.name} onClick={() => setDimension(d)} className={`flex items-center justify-center p-2 rounded-lg transition-all border-2 ${dimension.name === d.name ? 'border-cyan-400 bg-cyan-400/20 shadow-lg shadow-cyan-500/20' : 'border-slate-700 bg-slate-900/70 hover:bg-slate-700/50'}`} title={d.name}>
                        {d.icon}
                      </button>
                    ))}
                  </div>
                </div>
                 <div>
                  <label htmlFor="batchCount" className="block text-sm font-medium text-purple-300 mb-2">4. 批量生成</label>
                  <input
                    type="number"
                    id="batchCount"
                    value={batchCount}
                    min="1"
                    max="10"
                    onChange={e => setBatchCount(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                    className="w-full bg-slate-900/70 border border-slate-700 rounded-lg p-2.5 text-center focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 transition"
                  />
                </div>
              </div>

              {/* Generate Button */}
              <button
                onClick={generateImages}
                disabled={isLoading}
                className="w-full text-lg font-bold py-3 px-4 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 shadow-[0_0_20px_rgba(56,189,248,0.3)]"
              >
                {isLoading ? '生成中...' : '🚀 開始生成'}
              </button>
            </div>

            {/* History Panel */}
            <div className="p-6 bg-slate-800/50 backdrop-blur-md rounded-xl ring-1 ring-white/10">
              <h2 className="text-xl font-bold text-purple-300 mb-4">歷史紀錄</h2>
              <div className="max-h-96 space-y-3 overflow-y-auto pr-2">
                {history.length > 0 ? history.map(img => (
                  <HistoryItem key={img.id} image={img} onDownload={handleDownload} onPreview={setPreviewImage} />
                )) : (
                  <p className="text-center text-slate-400 py-8">還沒有歷史紀錄</p>
                )}
              </div>
            </div>
          </div>
          
          {/* Right Panel: Image Display */}
          <div className="lg:col-span-2 min-h-[60vh] lg:min-h-0 bg-slate-900/30 backdrop-blur-sm rounded-xl p-6 ring-1 ring-white/10 flex items-center justify-center">
            {isLoading ? (
              <Spinner />
            ) : generatedImages.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 w-full h-full overflow-y-auto pr-2">
                {generatedImages.map(img => (
                  <ImageCard key={img.id} image={img} onDownload={handleDownload} />
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-400">
                <p className="text-2xl mb-4">🎨</p>
                <h3 className="text-xl font-semibold">準備好創造藝術了嗎？</h3>
                <p>生成的圖像將會顯示在這裡</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
};

export default App;
