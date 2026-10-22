import type { Announcement, ClassSession, LectureNote, ProcessingStage, Student } from '@/types'

export const demoStudent: Student = {
  id: 'stu-001',
  name: 'Ayesha Khan',
  email: 'ayesha.khan@student.edu',
  avatarInitials: 'AK',
  program: 'BS Computer Science',
}

export const mockClasses: ClassSession[] = [
  {
    id: 'cls-001',
    title: 'Convolutional Neural Networks',
    subject: 'Deep Learning',
    date: '2026-09-16T10:00:00',
    durationMinutes: 62,
    status: 'completed',
    meetingLink: 'https://meet.example.com/dl-cnn-101',
    hasNotes: true,
  },
  {
    id: 'cls-002',
    title: 'Recurrent Networks & LSTMs',
    subject: 'Deep Learning',
    date: '2026-09-14T10:00:00',
    durationMinutes: 58,
    status: 'completed',
    meetingLink: 'https://meet.example.com/dl-rnn-102',
    hasNotes: true,
  },
  {
    id: 'cls-003',
    title: 'Database Normalization',
    subject: 'Databases',
    date: '2026-09-12T13:00:00',
    durationMinutes: 45,
    status: 'completed',
    meetingLink: 'https://meet.example.com/db-norm-201',
    hasNotes: true,
  },
  {
    id: 'cls-004',
    title: 'Transformer Architectures',
    subject: 'Deep Learning',
    date: '2026-09-19T10:00:00',
    status: 'upcoming',
    meetingLink: 'https://meet.example.com/dl-transformers-103',
    hasNotes: false,
  },
  {
    id: 'cls-005',
    title: 'Process Synchronization',
    subject: 'Operating Systems',
    date: '2026-09-10T09:00:00',
    durationMinutes: 50,
    status: 'completed',
    meetingLink: 'https://meet.example.com/os-sync-301',
    hasNotes: true,
  },
]

export const mockNotes: LectureNote[] = [
  {
    id: 'note-001',
    classId: 'cls-001',
    title: 'Convolutional Neural Networks',
    subject: 'Deep Learning',
    date: '2026-09-16T10:00:00',
    preview:
      'Covers convolution operations, filters, pooling layers, and how CNNs build spatial feature hierarchies for image tasks.',
    summary:
      'The lecture introduced convolutional neural networks as a feature-extraction approach for grid-like data such as images. It walked through convolution operations, stride and padding, pooling for spatial down-sampling, and how stacked layers build increasingly abstract feature hierarchies before a fully connected classification head.',
    topics: ['Convolution operation', 'Stride & padding', 'Pooling layers', 'Feature hierarchies', 'Parameter sharing'],
    sections: [
      {
        heading: 'Why Convolutions',
        points: [
          'Fully connected layers do not scale to image-sized inputs.',
          'Convolutions exploit local spatial structure and share parameters across positions.',
          'Fewer parameters reduce overfitting compared to dense layers on raw pixels.',
        ],
      },
      {
        heading: 'Core Operations',
        points: [
          'A filter (kernel) slides across the input, producing a feature map.',
          'Stride controls how far the filter moves each step.',
          'Padding preserves spatial dimensions at the image border.',
        ],
      },
      {
        heading: 'Pooling & Hierarchies',
        points: [
          'Max pooling keeps the strongest activation in a region, discarding the rest.',
          'Early layers learn edges and textures; deeper layers learn shapes and objects.',
          'Pooling reduces spatial size while keeping the most salient signal.',
        ],
      },
    ],
  },
  {
    id: 'note-002',
    classId: 'cls-002',
    title: 'Recurrent Networks & LSTMs',
    subject: 'Deep Learning',
    date: '2026-09-14T10:00:00',
    preview:
      'Explains sequence modeling, the vanishing gradient problem in vanilla RNNs, and how LSTM gates address it.',
    summary:
      'This session covered why standard feed-forward networks are unsuited to sequential data, how recurrent connections carry state across time steps, and why vanilla RNNs struggle with long-range dependencies. LSTM gating mechanisms were introduced as the standard fix, along with a brief comparison to GRUs.',
    topics: ['Sequence modeling', 'Hidden state', 'Vanishing gradients', 'LSTM gates', 'GRU comparison'],
    sections: [
      {
        heading: 'Sequential Data',
        points: [
          'RNNs maintain a hidden state that is updated at every time step.',
          'The same weights are reused across time steps, unlike a plain feed-forward stack.',
        ],
      },
      {
        heading: 'The Vanishing Gradient Problem',
        points: [
          'Gradients shrink exponentially as they are backpropagated through many time steps.',
          'This makes it hard for vanilla RNNs to learn long-range dependencies.',
        ],
      },
      {
        heading: 'LSTM Gates',
        points: [
          'Forget gate decides what to discard from the cell state.',
          'Input gate decides what new information to store.',
          'Output gate controls what part of the cell state is exposed as output.',
        ],
      },
    ],
  },
  {
    id: 'note-003',
    classId: 'cls-003',
    title: 'Database Normalization',
    subject: 'Databases',
    date: '2026-09-12T13:00:00',
    preview: 'Walks through 1NF, 2NF, 3NF with examples of redundancy removal and functional dependencies.',
    summary:
      'The lecture reviewed why normalization matters for reducing data redundancy and update anomalies, then worked through 1NF, 2NF, and 3NF with worked examples of splitting tables based on functional dependencies.',
    topics: ['Functional dependencies', '1NF', '2NF', '3NF', 'Update anomalies'],
    sections: [
      {
        heading: 'Why Normalize',
        points: [
          'Redundant data increases storage and risk of inconsistent updates.',
          'Normalization organizes columns and tables to minimize duplication.',
        ],
      },
      {
        heading: 'Normal Forms',
        points: [
          '1NF: eliminate repeating groups, ensure atomic column values.',
          '2NF: remove partial dependencies on a composite key.',
          '3NF: remove transitive dependencies between non-key columns.',
        ],
      },
    ],
  },
  {
    id: 'note-005',
    classId: 'cls-005',
    title: 'Process Synchronization',
    subject: 'Operating Systems',
    date: '2026-09-10T09:00:00',
    preview: 'Covers race conditions, critical sections, mutex locks, and the classic producer-consumer problem.',
    summary:
      'This lecture explained why concurrent access to shared data causes race conditions, defined the critical section problem, and covered mutex locks and semaphores as solutions, illustrated with the producer-consumer problem.',
    topics: ['Race conditions', 'Critical sections', 'Mutex locks', 'Semaphores', 'Producer-consumer problem'],
    sections: [
      {
        heading: 'Race Conditions',
        points: [
          'Occur when multiple processes access shared data concurrently without coordination.',
          'The final outcome depends on the particular order of execution.',
        ],
      },
      {
        heading: 'Solutions',
        points: [
          'Mutex locks allow only one process into the critical section at a time.',
          'Semaphores generalize this to allow a fixed number of concurrent accesses.',
        ],
      },
    ],
  },
]

export const mockAnnouncements: Announcement[] = [
  {
    id: 'ann-001',
    text: 'Assignment 3 on CNN architectures is posted. Submit a working notebook plus a one-page write-up.',
    category: 'Assignment',
    relatedLecture: 'Convolutional Neural Networks',
    relatedClassId: 'cls-001',
    date: '2026-09-16T10:52:00',
    deadline: '2026-09-23T23:59:00',
  },
  {
    id: 'ann-002',
    text: 'Short quiz on convolution arithmetic (stride, padding, output size) at the start of next class.',
    category: 'Quiz',
    relatedLecture: 'Convolutional Neural Networks',
    relatedClassId: 'cls-001',
    date: '2026-09-16T11:00:00',
  },
  {
    id: 'ann-003',
    text: 'Midterm exam will cover everything through Recurrent Networks & LSTMs, including this week’s material.',
    category: 'Exam',
    relatedLecture: 'Recurrent Networks & LSTMs',
    relatedClassId: 'cls-002',
    date: '2026-09-14T11:05:00',
    deadline: '2026-09-29T09:00:00',
  },
  {
    id: 'ann-004',
    text: 'Database normalization case-study submission deadline moved earlier due to the holiday.',
    category: 'Deadline',
    relatedLecture: 'Database Normalization',
    relatedClassId: 'cls-003',
    date: '2026-09-12T14:10:00',
    deadline: '2026-09-18T23:59:00',
  },
  {
    id: 'ann-005',
    text: 'Next week’s Deep Learning class is moved from Thursday to Friday, same time slot.',
    category: 'Schedule Change',
    relatedLecture: 'Recurrent Networks & LSTMs',
    relatedClassId: 'cls-002',
    date: '2026-09-14T11:10:00',
  },
  {
    id: 'ann-006',
    text: 'Office hours this week are extended by 30 minutes to accommodate assignment questions.',
    category: 'General Announcement',
    relatedLecture: 'Process Synchronization',
    relatedClassId: 'cls-005',
    date: '2026-09-10T10:00:00',
  },
]

export const processingStages: ProcessingStage[] = [
  { key: 'preparing', label: 'Preparing lecture content' },
  { key: 'transcribing', label: 'Transcribing audio' },
  { key: 'analyzing', label: 'Analyzing lecture content' },
  { key: 'identifying', label: 'Identifying important concepts' },
  { key: 'extracting', label: 'Extracting announcements' },
  { key: 'generating', label: 'Generating lecture notes' },
]
