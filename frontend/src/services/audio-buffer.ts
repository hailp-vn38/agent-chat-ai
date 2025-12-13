/**
 * Audio Buffering utilities for handling WebSocket audio packets
 * Implements BlockingQueue pattern for smooth audio streaming
 */

export interface DequeuedData<T> {
  items: T[];
  timedOut: boolean;
}

type TimerId = ReturnType<typeof setTimeout>;

export class BlockingQueue<T> {
  private items: T[] = [];
  private waiters: Array<{
    resolve: (items: T[]) => void;
    min: number;
    timer?: TimerId;
  }> = [];
  private maxSize = 1000; // Max items before discarding old frames

  /**
   * Add item(s) to queue
   */
  enqueue(...items: T[]): void {
    const validItems = items.filter(
      (item) => item !== null && item !== undefined
    );

    if (validItems.length === 0) return;

    this.items.push(...validItems);

    // Enforce max size - discard oldest items if exceeded
    if (this.items.length > this.maxSize) {
      const excess = this.items.length - this.maxSize;
      this.items = this.items.slice(excess);
    }

    // Wake up waiting consumers
    this.wakeWaiters();
  }

  /**
   * Get item(s) from queue or wait with timeout
   */
  async dequeue(min: number = 1, timeout: number = Infinity): Promise<T[]> {
    // If we already have enough items, return immediately
    if (this.items.length >= min) {
      return this.flush();
    }

    // Otherwise, wait for items to arrive
    return new Promise((resolve) => {
      let timer: TimerId | undefined;

      if (Number.isFinite(timeout) && timeout > 0) {
        timer = setTimeout(() => {
          this.removeWaiter(waiter);
          resolve(this.flush());
        }, timeout);
      }

      const waiter = { resolve, min, timer };
      this.waiters.push(waiter);
    });
  }

  /**
   * Get current queue size
   */
  get length(): number {
    return this.items.length;
  }

  /**
   * Clear all items
   */
  clear(): void {
    this.items = [];
  }

  /**
   * Private: flush all items and return
   */
  private flush(): T[] {
    const result = [...this.items];
    this.items = [];
    return result;
  }

  /**
   * Private: wake up waiters whose conditions are satisfied
   */
  private wakeWaiters(): void {
    for (let i = this.waiters.length - 1; i >= 0; i--) {
      const waiter = this.waiters[i];
      if (this.items.length >= waiter.min) {
        this.removeWaiter(waiter);
        waiter.resolve(this.flush());
      }
    }
  }

  /**
   * Private: remove waiter and cancel timeout
   */
  private removeWaiter(waiter: (typeof this.waiters)[0]): void {
    const idx = this.waiters.indexOf(waiter);
    if (idx !== -1) {
      this.waiters.splice(idx, 1);
      if (waiter.timer) {
        clearTimeout(waiter.timer);
      }
    }
  }
}

/**
 * Audio buffer queue for managing Opus packets
 */
export class AudioBuffer {
  private queue = new BlockingQueue<Uint8Array>();
  private readonly minBufferPackets = 3; // Minimum packets before playback
  private readonly bufferTimeoutMs = 300; // Max wait for buffer before playback starts

  /**
   * Add Opus packet to buffer
   */
  enqueue(packet: Uint8Array): void {
    this.queue.enqueue(packet);
  }

  /**
   * Get packets from buffer (blocking with timeout)
   */
  async dequeue(
    minPackets: number = this.minBufferPackets,
    timeoutMs: number = this.bufferTimeoutMs
  ): Promise<Uint8Array[]> {
    const result = await this.queue.dequeue(minPackets, timeoutMs);
    return result;
  }

  /**
   * Get current buffer size (number of packets)
   */
  get size(): number {
    return this.queue.length;
  }

  /**
   * Clear buffer
   */
  clear(): void {
    this.queue.clear();
  }

  /**
   * Check if buffer has sufficient data for playback
   */
  hasEnoughData(): boolean {
    return this.queue.length >= this.minBufferPackets;
  }
}
