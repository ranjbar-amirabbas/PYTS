namespace TranscriptionApi.Services;

using Microsoft.Extensions.Logging;
using System.Runtime.InteropServices;
using TranscriptionApi.Models;
using Whisper.net;
using Whisper.net.Ggml;

/// <summary>
/// Implementation of Whisper model service.
/// Manages the lifecycle of the Whisper speech recognition model and performs transcription.
/// </summary>
public class WhisperModelService : IWhisperModelService, IDisposable
{
    private readonly ILogger<WhisperModelService> _logger;
    private readonly AppConfiguration _config;
    private readonly SemaphoreSlim _loadLock;
    
    private WhisperProcessor? _processor;
    private bool _isLoaded;
    private bool _disposed;
    
    public WhisperModelService(ILogger<WhisperModelService> logger, AppConfiguration config)
    {
        _logger = logger;
        _config = config;
        _loadLock = new SemaphoreSlim(1, 1);
        _isLoaded = false;
        _disposed = false;
    }
    
    /// <inheritdoc/>
    public bool IsLoaded => _isLoaded;
    
    /// <inheritdoc/>
    public string ModelSize => _config.WhisperModelSize;
    
    /// <inheritdoc/>
    public async Task LoadModelAsync()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(WhisperModelService));
        }
        
        // Acquire the lock to ensure thread-safe loading
        await _loadLock.WaitAsync();
        try
        {
            // Check if already loaded (double-check pattern)
            if (_isLoaded)
            {
                _logger.LogInformation("Model loading: ALREADY_LOADED - Model {ModelSize} is already loaded, skipping", _config.WhisperModelSize);
                return;
            }
            
            _logger.LogInformation(
                "Model loading: STARTED - ModelSize: {ModelSize}. This may take several minutes on first run...",
                _config.WhisperModelSize);
            
            var loadStartTime = DateTime.UtcNow;
            
            // Parse the model size from configuration
            var ggmlType = ParseModelSize(_config.WhisperModelSize);
            _logger.LogDebug("Model loading: PARSED_MODEL_TYPE - GgmlType: {GgmlType}", ggmlType);
            
            // Determine model cache directory
            var homeDir = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            var cacheDir = Path.Combine(homeDir, ".cache", "whisper");
            Directory.CreateDirectory(cacheDir);
            
            var modelFileName = $"ggml-{_config.WhisperModelSize}.bin";
            var modelFilePath = Path.Combine(cacheDir, modelFileName);
            
            _logger.LogInformation(
                "Model loading: CACHE_DIR - CacheDirectory: {CacheDir}, ModelFile: {ModelFileName}",
                cacheDir,
                modelFileName);
            
            // Download the model if not already cached
            if (!File.Exists(modelFilePath))
            {
                _logger.LogInformation(
                    "Model loading: DOWNLOAD_STARTED - ModelFile: {ModelFilePath} not found in cache, downloading...",
                    modelFilePath);
                
                var downloadStartTime = DateTime.UtcNow;
                
                using var modelStream = await WhisperGgmlDownloader.Default.GetGgmlModelAsync(ggmlType);
                using var fileWriter = File.OpenWrite(modelFilePath);
                await modelStream.CopyToAsync(fileWriter);
                
                var downloadDuration = DateTime.UtcNow - downloadStartTime;
                var fileInfo = new FileInfo(modelFilePath);
                
                _logger.LogInformation(
                    "Model loading: DOWNLOAD_COMPLETED - ModelFile: {ModelFilePath}, Size: {FileSize} bytes, Duration: {Duration}ms",
                    modelFilePath,
                    fileInfo.Length,
                    downloadDuration.TotalMilliseconds);
            }
            else
            {
                var fileInfo = new FileInfo(modelFilePath);
                _logger.LogInformation(
                    "Model loading: USING_CACHED - ModelFile: {ModelFilePath}, Size: {FileSize} bytes",
                    modelFilePath,
                    fileInfo.Length);
                
                // Verify the model file is valid by checking its size
                // Medium model should be around 1.5GB, but GGML quantized versions can be smaller
                if (fileInfo.Length < 100_000_000) // Less than 100MB is suspicious
                {
                    _logger.LogWarning(
                        "Model loading: SUSPICIOUS_FILE_SIZE - ModelFile: {ModelFilePath} seems too small ({FileSize} bytes), deleting and re-downloading...",
                        modelFilePath,
                        fileInfo.Length);
                    
                    File.Delete(modelFilePath);
                    
                    var downloadStartTime = DateTime.UtcNow;
                    using var modelStream = await WhisperGgmlDownloader.Default.GetGgmlModelAsync(ggmlType);
                    using var fileWriter = File.OpenWrite(modelFilePath);
                    await modelStream.CopyToAsync(fileWriter);
                    
                    var downloadDuration = DateTime.UtcNow - downloadStartTime;
                    var newFileInfo = new FileInfo(modelFilePath);
                    
                    _logger.LogInformation(
                        "Model loading: REDOWNLOAD_COMPLETED - ModelFile: {ModelFilePath}, Size: {FileSize} bytes, Duration: {Duration}ms",
                        modelFilePath,
                        newFileInfo.Length,
                        downloadDuration.TotalMilliseconds);
                }
            }
            
            // Create the Whisper processor using the factory
            _logger.LogDebug("Model loading: PROCESSOR_CREATION_STARTED - Creating WhisperProcessor from {ModelFilePath}", modelFilePath);
            
            var processorStartTime = DateTime.UtcNow;
            
            try
            {
                var whisperFactory = WhisperFactory.FromPath(modelFilePath);
                
                // Log system information for debugging
                _logger.LogInformation(
                    "Model loading: SYSTEM_INFO - OS: {OS}, Architecture: {Arch}, ProcessorCount: {Processors}",
                    Environment.OSVersion,
                    RuntimeInformation.ProcessArchitecture,
                    Environment.ProcessorCount);
                
                _processor = whisperFactory.CreateBuilder()
                    .WithLanguage("auto") // Auto-detect language
                    .Build();
            }
            catch (Exception factoryEx)
            {
                _logger.LogError(factoryEx, "Failed to create WhisperFactory or build processor. Inner exception: {InnerException}", factoryEx.InnerException?.Message);
                throw;
            }
            
            var processorDuration = DateTime.UtcNow - processorStartTime;
            _logger.LogDebug(
                "Model loading: PROCESSOR_CREATION_COMPLETED - Duration: {Duration}ms",
                processorDuration.TotalMilliseconds);
            
            _isLoaded = true;
            
            var totalDuration = DateTime.UtcNow - loadStartTime;
            _logger.LogInformation(
                "Model loading: COMPLETED - ModelSize: {ModelSize}, TotalDuration: {Duration}ms, IsLoaded: {IsLoaded}",
                _config.WhisperModelSize,
                totalDuration.TotalMilliseconds,
                _isLoaded);
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex,
                "Model loading: FAILED - ModelSize: {ModelSize}, Error: {ErrorMessage}",
                _config.WhisperModelSize,
                ex.Message);
            
            _isLoaded = false;
            _processor?.Dispose();
            _processor = null;
            throw new InvalidOperationException($"Failed to load Whisper model: {ex.Message}", ex);
        }
        finally
        {
            _loadLock.Release();
        }
    }
    
    /// <inheritdoc/>
    public async Task<string> TranscribeAsync(string audioFilePath, CancellationToken ct)
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(WhisperModelService));
        }
        
        // Ensure model is loaded
        if (!_isLoaded || _processor == null)
        {
            _logger.LogWarning("Model transcription: MODEL_NOT_LOADED - Attempted to transcribe before model was loaded, loading now...");
            await LoadModelAsync();
        }
        
        if (_processor == null)
        {
            throw new InvalidOperationException("Whisper model is not loaded");
        }
        
        try
        {
            if (!File.Exists(audioFilePath))
            {
                throw new FileNotFoundException($"Audio file not found: {audioFilePath}");
            }
            
            var fileInfo = new FileInfo(audioFilePath);
            _logger.LogInformation(
                "Model transcription: STARTED - AudioFile: {AudioFilePath}, Size: {FileSize} bytes",
                audioFilePath,
                fileInfo.Length);
            
            var startTime = DateTime.UtcNow;
            
            // Process the audio file and collect transcription segments
            var transcriptionBuilder = new System.Text.StringBuilder();
            var segmentCount = 0;
            
            using var fileStream = File.OpenRead(audioFilePath);
            await foreach (var segment in _processor.ProcessAsync(fileStream, ct))
            {
                transcriptionBuilder.Append(segment.Text);
                segmentCount++;
                
                _logger.LogDebug(
                    "Model transcription: SEGMENT_PROCESSED - AudioFile: {AudioFilePath}, SegmentNumber: {SegmentNumber}, SegmentText: {SegmentText}",
                    audioFilePath,
                    segmentCount,
                    segment.Text);
            }
            
            var transcription = transcriptionBuilder.ToString().Trim();
            var duration = DateTime.UtcNow - startTime;
            
            _logger.LogInformation(
                "Model transcription: COMPLETED - AudioFile: {AudioFilePath}, Duration: {Duration}ms, Segments: {SegmentCount}, ResultLength: {Length} characters",
                audioFilePath,
                duration.TotalMilliseconds,
                segmentCount,
                transcription.Length);
            
            return transcription;
        }
        catch (OperationCanceledException)
        {
            _logger.LogWarning(
                "Model transcription: CANCELLED - AudioFile: {AudioFilePath}",
                audioFilePath);
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex,
                "Model transcription: FAILED - AudioFile: {AudioFilePath}, Error: {ErrorMessage}",
                audioFilePath,
                ex.Message);
            throw new InvalidOperationException($"Transcription failed: {ex.Message}", ex);
        }
    }
    
    /// <summary>
    /// Parses the model size string into a GgmlType enum value.
    /// </summary>
    /// <param name="modelSize">The model size string (e.g., "tiny", "base", "small", "medium", "large")</param>
    /// <returns>The corresponding GgmlType enum value</returns>
    /// <exception cref="ArgumentException">Thrown when the model size is not recognized</exception>
    private GgmlType ParseModelSize(string modelSize)
    {
        return modelSize.ToLowerInvariant() switch
        {
            "tiny" => GgmlType.Tiny,
            "base" => GgmlType.Base,
            "small" => GgmlType.Small,
            "medium" => GgmlType.Medium,
            "large" => GgmlType.LargeV3,
            _ => throw new ArgumentException(
                $"Invalid model size: {modelSize}. Valid values: tiny, base, small, medium, large",
                nameof(modelSize))
        };
    }
    
    /// <summary>
    /// Disposes of the Whisper model resources.
    /// </summary>
    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        
        _logger.LogInformation("Disposing WhisperModelService and cleaning up resources");
        
        _processor?.Dispose();
        _processor = null;
        _loadLock?.Dispose();
        _isLoaded = false;
        _disposed = true;
        
        GC.SuppressFinalize(this);
    }
}
