export type LiveAudioStatus = 'idle' | 'recording' | 'paused' | 'stopped' | 'error'

export interface LiveAudioState {
  status: LiveAudioStatus
  durationSeconds: number
  error?: string
}

export class LiveAudioService {
  private mediaRecorder: MediaRecorder | null = null
  private stream: MediaStream | null = null
  private chunks: Blob[] = []
  private timer: number | null = null
  private startTime = 0
  private duration = 0
  private stopPromise: Promise<File | null> | null = null

  private onStateChange: (state: LiveAudioState) => void

  constructor(onStateChange: (state: LiveAudioState) => void) {
    this.onStateChange = onStateChange
  }

  async start(): Promise<void> {
    if (this.mediaRecorder?.state === 'recording') {
      return
    }

    this.cleanup()

    try {
      this.stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      })

      const audioTrack = this.stream.getAudioTracks()[0]

      if (!audioTrack) {
        this.stream.getTracks().forEach((track) => track.stop())
        this.stream = null
        throw new Error(
          'No audio track found. Select the meeting tab and enable "Share tab audio".',
        )
      }

      const videoTracks = this.stream.getVideoTracks()
      videoTracks.forEach((track) => track.stop())

      audioTrack.onended = () => {
        if (this.mediaRecorder?.state === 'recording') {
          void this.stop()
        }
      }

      const recorderStream = new MediaStream([audioTrack])

      const mimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
      ]

      const supportedMimeType = mimeTypes.find((type) =>
        MediaRecorder.isTypeSupported(type),
      )

      this.mediaRecorder = supportedMimeType
        ? new MediaRecorder(recorderStream, { mimeType: supportedMimeType })
        : new MediaRecorder(recorderStream)

      this.chunks = []

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.chunks.push(event.data)
        }
      }

      this.mediaRecorder.onstop = () => {
        this.stopTimer()
        this.onStateChange({
          status: 'stopped',
          durationSeconds: this.duration,
        })
      }

      this.mediaRecorder.onerror = () => {
        this.stopTimer()
        this.onStateChange({
          status: 'error',
          durationSeconds: this.duration,
          error: 'Audio recording failed.',
        })
      }

      this.mediaRecorder.start(1000)

      this.startTime = Date.now()
      this.duration = 0
      this.startTimer()

      this.onStateChange({
        status: 'recording',
        durationSeconds: 0,
      })
    } catch (err) {
      this.cleanup()

      const message =
        err instanceof Error
          ? err.message
          : 'Could not start live capture.'

      this.onStateChange({
        status: 'error',
        durationSeconds: 0,
        error: message,
      })

      throw err
    }
  }

  async stop(filename = `live_${Date.now()}.webm`): Promise<File | null> {
    if (this.stopPromise) {
      return this.stopPromise
    }

    const recorder = this.mediaRecorder

    if (!recorder || recorder.state === 'inactive') {
      this.stopTimer()
      return this.chunks.length > 0
        ? this.getFile(filename)
        : null
    }

    this.stopPromise = new Promise<File | null>((resolve) => {
      recorder.addEventListener(
        'stop',
        () => {
          const blob = new Blob(this.chunks, {
            type: recorder.mimeType || 'audio/webm',
          })

          this.stopTimer()

          const file =
            blob.size > 0
              ? new File([blob], filename, {
                  type: blob.type || 'audio/webm',
                })
              : null

          this.stream?.getTracks().forEach((track) => track.stop())

          this.stream = null
          this.mediaRecorder = null
          this.stopPromise = null

          resolve(file)
        },
        { once: true },
      )

      recorder.stop()
    })

    return this.stopPromise
  }

  getBlob(): Blob {
    return new Blob(this.chunks, { type: 'audio/webm' })
  }

  getFile(filename = `live_${Date.now()}.webm`): File | null {
    const blob = this.getBlob()

    if (blob.size === 0) {
      return null
    }

    return new File([blob], filename, {
      type: blob.type || 'audio/webm',
    })
  }

  private startTimer() {
    this.stopTimer()

    this.timer = window.setInterval(() => {
      this.duration = Math.floor((Date.now() - this.startTime) / 1000)

      this.onStateChange({
        status: 'recording',
        durationSeconds: this.duration,
      })
    }, 1000)
  }

  private stopTimer() {
    if (this.timer !== null) {
      window.clearInterval(this.timer)
      this.timer = null
    }
  }

  private cleanup() {
    this.stopTimer()

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop())
    }

    this.stream = null
    this.mediaRecorder = null
    this.chunks = []
    this.stopPromise = null
  }
}
