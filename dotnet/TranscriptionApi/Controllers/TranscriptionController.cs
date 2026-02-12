namespace TranscriptionApi.Controllers;

using Microsoft.AspNetCore.Mvc;
using TranscriptionApi.Exceptions;
using TranscriptionApi.Models;
using TranscriptionApi.Services;

/// <summary>
/// Controller for batch transcription operations.
/// Handles audio file uploads and job status queries.
/// </summary>
[ApiController]
[Route("api/v1/transcribe")]
public class TranscriptionController : ControllerBase
{
    private readonly ITranscriptionService _transcriptionService;
    private readonly IJobManager _jobManager;
    private readonly IAudioProcessor _audioProcessor;
    private readonly ILogger<TranscriptionController> _logger;

    public TranscriptionController(
        ITranscriptionService transcriptionService,
        IJobManager jobManager,
        IAudioProcessor audioProcessor,
        ILogger<TranscriptionController> logger)
    {
        _transcriptionService = transcriptionService;
        _jobManager = jobManager;
        _audioProcessor = audioProcessor;
        _logger = logger;
    }

    /// <summary>
    /// Submit an audio file for batch transcription.
    /// Creates a job and starts background processing.
    /// </summary>
    /// <param name="audioFile">The audio file to transcribe (WAV, MP3, OGG, M4A)</param>
    /// <param name="ct">Cancellation token</param>
    /// <returns>Job ID and status</returns>
    /// <response code="200">Job created successfully</response>
    /// <response code="413">File exceeds maximum size limit</response>
    /// <response code="415">Unsupported audio format</response>
    /// <response code="503">Service at capacity</response>
    [HttpPost("batch")]
    [ProducesResponseType(typeof(BatchTranscriptionResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status413PayloadTooLarge)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status415UnsupportedMediaType)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status503ServiceUnavailable)]
    public async Task<ActionResult<BatchTranscriptionResponse>> SubmitBatchJob(
        IFormFile audioFile,
        CancellationToken ct)
    {
        _logger.LogInformation("Received batch transcription request for file: {FileName}", audioFile?.FileName);

        // Validate that a file was provided
        if (audioFile == null || audioFile.Length == 0)
        {
            _logger.LogWarning("No audio file provided in request");
            throw new InvalidAudioFormatException("No audio file provided");
        }

        // Validate audio file format and size
        // This will throw InvalidAudioFormatException or FileTooLargeException if validation fails
        _audioProcessor.IsValidAudioFile(audioFile);
        _logger.LogDebug("Audio file validation passed for: {FileName}", audioFile.FileName);

        // Check capacity before accepting the job
        if (_jobManager.IsAtCapacity())
        {
            _logger.LogWarning("Service at capacity, rejecting new job request");
            throw new ServiceAtCapacityException("Service is at capacity. Please try again later.");
        }

        // Save the uploaded file to temporary storage
        string audioFilePath;
        try
        {
            audioFilePath = await _audioProcessor.SaveUploadedFileAsync(audioFile, ct);
            _logger.LogDebug("Audio file saved to: {FilePath}", audioFilePath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to save uploaded audio file: {FileName}", audioFile.FileName);
            throw new InvalidOperationException("Failed to save uploaded file", ex);
        }

        // Create a new job with pending status
        string jobId = _jobManager.CreateJob();
        _logger.LogInformation("Created job {JobId} for file: {FileName}", jobId, audioFile.FileName);

        // Start background processing (fire and forget)
        _ = _jobManager.StartJobProcessingAsync(jobId, audioFilePath);
        _logger.LogDebug("Started background processing for job {JobId}", jobId);

        // Return job ID and status immediately
        return Ok(new BatchTranscriptionResponse(
            JobId: jobId,
            Status: "pending"
        ));
    }
    /// <summary>
    /// Transcribe an audio file synchronously and return the result immediately.
    /// This endpoint waits for the transcription to complete before returning.
    /// </summary>
    /// <param name="audioFile">The audio file to transcribe (WAV, MP3, OGG, M4A)</param>
    /// <param name="ct">Cancellation token</param>
    /// <returns>Transcription result</returns>
    /// <response code="200">Transcription completed successfully</response>
    /// <response code="413">File exceeds maximum size limit</response>
    /// <response code="415">Unsupported audio format</response>
    [HttpPost("sync")]
    [ProducesResponseType(typeof(SyncTranscriptionResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status413PayloadTooLarge)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status415UnsupportedMediaType)]
    public async Task<ActionResult<SyncTranscriptionResponse>> TranscribeSync(
        IFormFile audioFile,
        CancellationToken ct)
    {
        _logger.LogInformation("Received synchronous transcription request for file: {FileName}", audioFile?.FileName);

        // Validate that a file was provided
        if (audioFile == null || audioFile.Length == 0)
        {
            _logger.LogWarning("No audio file provided in request");
            throw new InvalidAudioFormatException("No audio file provided");
        }

        // Validate audio file format and size
        _audioProcessor.IsValidAudioFile(audioFile);
        _logger.LogDebug("Audio file validation passed for: {FileName}", audioFile.FileName);

        // Save the uploaded file to temporary storage
        string audioFilePath;
        try
        {
            audioFilePath = await _audioProcessor.SaveUploadedFileAsync(audioFile, ct);
            _logger.LogDebug("Audio file saved to: {FilePath}", audioFilePath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to save uploaded audio file: {FileName}", audioFile.FileName);
            throw new InvalidOperationException("Failed to save uploaded file", ex);
        }

        try
        {
            // Transcribe the audio file synchronously
            _logger.LogInformation("Starting synchronous transcription for file: {FileName}", audioFile.FileName);
            var transcription = await _transcriptionService.TranscribeAsync(audioFilePath, ct);
            _logger.LogInformation("Synchronous transcription completed for file: {FileName}", audioFile.FileName);

            return Ok(new SyncTranscriptionResponse(
                Transcription: transcription,
                Status: "completed"
            ));
        }
        finally
        {
            // Clean up the uploaded file
            try
            {
                 if (System.IO.File.Exists(audioFilePath))
                {
                    System.IO.File.Delete(audioFilePath);
                    _logger.LogDebug("Deleted uploaded audio file: {FilePath}", audioFilePath);
                }
            }
            catch (Exception cleanupEx)
            {
                _logger.LogWarning(cleanupEx, "Failed to clean up uploaded file: {FilePath}", audioFilePath);
            }
        }
    }


    /// <summary>
    /// Get the status and results of a transcription job.
    /// </summary>
    /// <param name="jobId">The unique job identifier</param>
    /// <returns>Job status and transcription results if available</returns>
    /// <response code="200">Job found and status returned</response>
    /// <response code="404">Job not found</response>
    [HttpGet("batch/{jobId}")]
    [ProducesResponseType(typeof(JobStatusResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ErrorResponse), StatusCodes.Status404NotFound)]
    public ActionResult<JobStatusResponse> GetJobStatus(string jobId)
    {
        _logger.LogInformation("Job status query for: {JobId}", jobId);

        // Look up the job
        var job = _jobManager.GetJob(jobId);
        
        if (job == null)
        {
            _logger.LogWarning("Job not found: {JobId}", jobId);
            throw new JobNotFoundException($"Job with ID '{jobId}' not found");
        }

        _logger.LogDebug("Job {JobId} status: {Status}", jobId, job.Status);

        // Map job status enum to string
        string statusString = job.Status switch
        {
            JobStatus.Pending => "pending",
            JobStatus.Processing => "processing",
            JobStatus.Completed => "completed",
            JobStatus.Failed => "failed",
            _ => "unknown"
        };

        // Return job status response
        return Ok(new JobStatusResponse(
            JobId: job.JobId,
            Status: statusString,
            Transcription: job.Transcription,
            Error: job.Error
        ));
    }
}
