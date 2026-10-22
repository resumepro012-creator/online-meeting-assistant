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
  private startTime: number = 0

  private onStateChange: (state: LiveAudioState) => void
  private duration: number = 0

  constructor(onStateChange: (state: LiveAudioState) => void) {
    this.onStateChange = onStateChange
  }

  async start(): Promise<void> {
    try {
      // getDisplayMedia is used to capture system/tab audio.
      // The user must select the tab where the meeting is happening.
      this.stream = await navigator.mediaDevices.getDisplayMedia({
        video: true, // Required for getDisplayMedia, but we'll only use audio
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      })

      const audioTrack = this.stream.getAudioTracks()[0]
      if (!audioTrack) {
        throw new Error('No audio track found. Make sure to check "Share tab audio".')
      }

      // We only care about audio, so we can stop the video track immediately
      // to reduce resource usage and avoid showing the "Screen Sharing" indicator too prominently.
      this.stream.getVideoTracks().forEach((track) => track.stop())

      this.mediaRecorder = new MediaRecorder(new MediaStream([audioTrack]), {
        mimeType: 'audio/webm;codecs=opus',
      })

      this.chunks = []
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.chunks.push(e.data)
      }

      this.mediaRecorder.onstop = () => {
        this.stopTimer()
        this.onStateChange({ status: 'stopped', durationSeconds: this.duration })
      }

      this.mediaRecorder.start(1000) // Capture in 1s chunks
      this.startTime = Date.now()
      this.startTimer()
      this.onStateChange({ status: 'recording', durationSeconds: 0 })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not start live capture'
      this.onStateChange({ status: 'error', durationSeconds: 0, error: message })
      throw err
    }
  }

  stop(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop())
    }
  }

  getBlob(): Blob {
    return new Blob(this.chunks, { type: 'audio/webm' })
  }

  getFile(filename: string = 'live_capture.webm'): File {
    const blob = this.getBlob()
    return new File([blob], filename, { type: 'audio/webm' })
  }

  private startTimer() {
    this.duration = 0
    this.timer = window.setInterval(() => {
      this.duration = Math.floor((Date.now() - this.startTime) / 1000)
      this.onStateChange({ status: 'recording', durationSeconds: this.duration })
    }, 1000)
  }

  private stopTimer() {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  }
}
