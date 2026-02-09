using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using TranscriptionApi.Models;
using TranscriptionApi.Services;

namespace TranscriptionApi.Controllers;

/// <summary>
/// Controller for handling real-time streaming transcription via WebSocket.
/// Accepts binary audio chunks, buffers them, and returns partial/final transcription results.
/// </summary>
[ApiController]
public class StreamingTranscriptionController : ControllerBase
{
    private readonly ITranscriptionService _transcriptionService;
    private readonly AppConfiguration _config;
    private readonly ILogger<StreamingTranscriptionController> _logger;

    public StreamingTranscriptionController(
        ITranscriptionService transcriptionService,
        AppConfiguration config,
        ILogger<StreamingTranscriptionController> logger)
    {
        _transcriptionService = transcriptionService;
        _config = config;
        _logger = logger;
    }

    /// <summary>
    /// WebSocket endpoint for streaming transcription.
    /// Accepts binary audio chunks and returns JSON transcription messages.
    /// </summary>
    /// <returns>WebSocket connection handling task</returns>
    [Route("/api/v1/transcribe/stream")]
    [ApiExplorerSettings(IgnoreApi = true)] // Exclude from Swagger - WebSocket endpoints not supported
    public async Task HandleWebSocket()
    {
        if (!HttpContext.WebSockets.IsWebSocketRequest)
        {
            HttpContext.Response.StatusCode = StatusCodes.Status400BadRequest;
            await HttpContext.Response.WriteAsync("WebSocket connection required");
            return;
        }

        using var webSocket = await HttpContext.WebSockets.AcceptWebSocketAsync();
        _logger.LogInformation("WebSocket connection established");

        await ProcessWebSocketConnection(webSocket);
    }

    /// <summary>
    /// Processes the WebSocket connection, handling audio chunks and transcription.
    /// </summary>
    /// <param name="webSocket">The WebSocket connection</param>
    private async Task ProcessWebSocketConnection(WebSocket webSocket)
    {
        var buffer = new List<byte>();
        var receiveBuffer = new byte[4096]; // 4KB receive buffer
        var cts = new CancellationTokenSource();

        try
        {
            while (webSocket.State == WebSocketState.Open)
            {
                var result = await webSocket.ReceiveAsync(
                    new ArraySegment<byte>(receiveBuffer),
                    cts.Token);

                if (result.MessageType == WebSocketMessageType.Close)
                {
                    _logger.LogInformation("WebSocket close message received");
                    
                    // Transcribe remaining buffer if any data exists
                    if (buffer.Count > 0)
                    {
                        await TranscribeAndSendFinal(webSocket, buffer.ToArray(), cts.Token);
                    }

                    await webSocket.CloseAsync(
                        WebSocketCloseStatus.NormalClosure,
                        "Connection closed",
                        cts.Token);
                    break;
                }

                if (result.MessageType == WebSocketMessageType.Binary)
                {
                    // Append received data to buffer
                    buffer.AddRange(receiveBuffer.Take(result.Count));
                    _logger.LogDebug("Received {ByteCount} bytes, buffer size: {BufferSize}", 
                        result.Count, buffer.Count);

                    // Check if buffer exceeds maximum size
                    if (buffer.Count > _config.StreamMaxBufferSize)
                    {
                        _logger.LogWarning("Buffer size {BufferSize} exceeds maximum {MaxSize}",
                            buffer.Count, _config.StreamMaxBufferSize);
                        
                        await SendErrorMessage(
                            webSocket,
                            "Buffer overflow: maximum buffer size exceeded",
                            cts.Token);
                        
                        await webSocket.CloseAsync(
                            WebSocketCloseStatus.MessageTooBig,
                            "Buffer overflow",
                            cts.Token);
                        break;
                    }

                    // Check if buffer has reached minimum chunk size for transcription
                    if (buffer.Count >= _config.StreamMinChunkSize)
                    {
                        _logger.LogInformation("Buffer reached minimum chunk size, transcribing {ByteCount} bytes",
                            buffer.Count);
                        
                        await TranscribeAndSendPartial(webSocket, buffer.ToArray(), cts.Token);
                        
                        // Clear buffer after successful transcription
                        buffer.Clear();
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
            _logger.LogInformation("WebSocket operation cancelled");
        }
        catch (WebSocketException ex)
        {
            _logger.LogError(ex, "WebSocket error occurred");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error during WebSocket processing");
            
            try
            {
                await SendErrorMessage(webSocket, "Internal server error", cts.Token);
            }
            catch
            {
                // Ignore errors when sending error message
            }
        }
        finally
        {
            cts.Dispose();
            _logger.LogInformation("WebSocket connection closed");
        }
    }

    /// <summary>
    /// Transcribes audio data and sends a partial result message.
    /// </summary>
    /// <param name="webSocket">The WebSocket connection</param>
    /// <param name="audioData">Audio data to transcribe</param>
    /// <param name="ct">Cancellation token</param>
    private async Task TranscribeAndSendPartial(WebSocket webSocket, byte[] audioData, CancellationToken ct)
    {
        try
        {
            var transcription = await _transcriptionService.TranscribeStreamAsync(audioData, ct);
            
            var message = new StreamingMessage(
                Type: "partial",
                Text: transcription,
                Timestamp: DateTimeOffset.UtcNow.ToUnixTimeSeconds()
            );

            await SendJsonMessage(webSocket, message, ct);
            
            _logger.LogInformation("Sent partial transcription: {Text}", transcription);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during partial transcription");
            await SendErrorMessage(webSocket, "Transcription failed", ct);
        }
    }

    /// <summary>
    /// Transcribes remaining audio data and sends a final result message.
    /// </summary>
    /// <param name="webSocket">The WebSocket connection</param>
    /// <param name="audioData">Audio data to transcribe</param>
    /// <param name="ct">Cancellation token</param>
    private async Task TranscribeAndSendFinal(WebSocket webSocket, byte[] audioData, CancellationToken ct)
    {
        try
        {
            var transcription = await _transcriptionService.TranscribeStreamAsync(audioData, ct);
            
            var message = new StreamingMessage(
                Type: "final",
                Text: transcription,
                Timestamp: DateTimeOffset.UtcNow.ToUnixTimeSeconds()
            );

            await SendJsonMessage(webSocket, message, ct);
            
            _logger.LogInformation("Sent final transcription: {Text}", transcription);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during final transcription");
            await SendErrorMessage(webSocket, "Final transcription failed", ct);
        }
    }

    /// <summary>
    /// Sends an error message over the WebSocket.
    /// </summary>
    /// <param name="webSocket">The WebSocket connection</param>
    /// <param name="errorText">Error message text</param>
    /// <param name="ct">Cancellation token</param>
    private async Task SendErrorMessage(WebSocket webSocket, string errorText, CancellationToken ct)
    {
        var message = new StreamingMessage(
            Type: "error",
            Text: errorText,
            Timestamp: DateTimeOffset.UtcNow.ToUnixTimeSeconds()
        );

        await SendJsonMessage(webSocket, message, ct);
    }

    /// <summary>
    /// Sends a JSON message over the WebSocket.
    /// </summary>
    /// <param name="webSocket">The WebSocket connection</param>
    /// <param name="message">Message to send</param>
    /// <param name="ct">Cancellation token</param>
    private async Task SendJsonMessage(WebSocket webSocket, StreamingMessage message, CancellationToken ct)
    {
        var json = JsonSerializer.Serialize(message, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        });
        
        var bytes = Encoding.UTF8.GetBytes(json);
        
        await webSocket.SendAsync(
            new ArraySegment<byte>(bytes),
            WebSocketMessageType.Text,
            endOfMessage: true,
            ct);
    }
}
