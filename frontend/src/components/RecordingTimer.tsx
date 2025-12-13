"use client";

import { useEffect, useRef, useState } from "react";
import { Square, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";

type RecordingTimerProps = {
  isRecording: boolean;
  isConnected: boolean;
  onToggleRecording: () => void;
};

export function RecordingTimer(props: RecordingTimerProps) {
  const [recordingTime, setRecordingTime] = useState(0);
  const recordingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(
    null
  );

  useEffect(() => {
    if (props.isRecording) {
      setRecordingTime(0);
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime((t) => t + 1);
      }, 1000);
    } else {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
      setRecordingTime(0);
    }

    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    };
  }, [props.isRecording]);

  return (
    <Button
      onClick={props.onToggleRecording}
      disabled={!props.isConnected}
      variant={props.isRecording ? "destructive" : "default"}
      size="sm"
      title={
        props.isRecording
          ? `Stop Recording (${recordingTime}s)`
          : "Start Recording"
      }
    >
      {props.isRecording ? (
        <Square className="w-4 h-4" />
      ) : (
        <Mic className="w-4 h-4" />
      )}
    </Button>
  );
}
