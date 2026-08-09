package com.robotemi.agent.camera;

import java.nio.ByteBuffer;

/** Copies one strided YUV_420_888 plane into a packed encoder buffer. */
final class Yuv420PlaneCopier {
    private Yuv420PlaneCopier() {}

    static void copy(
            ByteBuffer source,
            int sourceRowStride,
            int sourcePixelStride,
            int planeWidth,
            int planeHeight,
            byte[] target,
            int targetOffset,
            int targetRowStride,
            int targetPixelStride,
            byte[] scratchRow) {
        int sourceLimit = source.limit();

        if (sourcePixelStride == 1 && targetPixelStride == 1) {
            copyPackedRows(
                    source,
                    sourceRowStride,
                    planeWidth,
                    planeHeight,
                    target,
                    targetOffset,
                    targetRowStride,
                    sourceLimit);
            return;
        }

        if (scratchRow == null || scratchRow.length < sourceRowStride) {
            throw new IllegalArgumentException("scratchRow must cover sourceRowStride");
        }

        for (int row = 0; row < planeHeight; row++) {
            int sourceRowStart = row * sourceRowStride;
            int readLength = Math.min(sourceRowStride, sourceLimit - sourceRowStart);
            if (readLength <= 0) return;

            source.position(sourceRowStart);
            source.get(scratchRow, 0, readLength);

            int readableSamples = Math.min(
                    planeWidth,
                    (readLength + sourcePixelStride - 1) / sourcePixelStride);
            int sourceIndex = 0;
            int targetIndex = targetOffset + row * targetRowStride;
            for (int column = 0; column < readableSamples; column++) {
                target[targetIndex] = scratchRow[sourceIndex];
                sourceIndex += sourcePixelStride;
                targetIndex += targetPixelStride;
            }
        }
    }

    private static void copyPackedRows(
            ByteBuffer source,
            int sourceRowStride,
            int planeWidth,
            int planeHeight,
            byte[] target,
            int targetOffset,
            int targetRowStride,
            int sourceLimit) {
        for (int row = 0; row < planeHeight; row++) {
            int sourceRowStart = row * sourceRowStride;
            int copyLength = Math.min(planeWidth, sourceLimit - sourceRowStart);
            if (copyLength <= 0) return;

            source.position(sourceRowStart);
            source.get(target, targetOffset + row * targetRowStride, copyLength);
        }
    }
}
