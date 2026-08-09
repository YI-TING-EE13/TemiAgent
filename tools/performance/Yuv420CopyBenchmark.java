package com.robotemi.agent.camera;

import java.nio.ByteBuffer;
import java.util.Arrays;

/** Standalone benchmark for the CPU preprocessing performed before H.264 encoding. */
public final class Yuv420CopyBenchmark {
    private static final int WIDTH = 1280;
    private static final int HEIGHT = 720;
    private static final int FRAME_SIZE = WIDTH * HEIGHT * 3 / 2;
    private static volatile long blackhole;

    private interface Copier {
        void copy(Plane[] planes, byte[] target);
    }

    private static final class Plane {
        final ByteBuffer buffer;
        final int rowStride;
        final int pixelStride;

        Plane(ByteBuffer buffer, int rowStride, int pixelStride) {
            this.buffer = buffer;
            this.rowStride = rowStride;
            this.pixelStride = pixelStride;
        }
    }

    private static final class LegacyCopier implements Copier {
        private byte[] scratchRow;

        @Override
        public void copy(Plane[] planes, byte[] target) {
            int ySize = WIDTH * HEIGHT;
            int chromaSize = ySize / 4;
            copyPlane(planes[0], WIDTH, HEIGHT, target, 0, WIDTH, 1);
            copyPlane(planes[1], WIDTH / 2, HEIGHT / 2, target, ySize, WIDTH / 2, 1);
            copyPlane(
                    planes[2],
                    WIDTH / 2,
                    HEIGHT / 2,
                    target,
                    ySize + chromaSize,
                    WIDTH / 2,
                    1);
        }

        private void copyPlane(
                Plane plane,
                int planeWidth,
                int planeHeight,
                byte[] target,
                int targetOffset,
                int targetRowStride,
                int targetPixelStride) {
            int sourceLimit = plane.buffer.limit();
            if (scratchRow == null || scratchRow.length < plane.rowStride) {
                scratchRow = new byte[plane.rowStride];
            }

            for (int row = 0; row < planeHeight; row++) {
                int sourceRowStart = row * plane.rowStride;
                int readLength = Math.min(plane.rowStride, sourceLimit - sourceRowStart);
                if (readLength <= 0) return;
                plane.buffer.position(sourceRowStart);
                plane.buffer.get(scratchRow, 0, readLength);
                for (int column = 0; column < planeWidth; column++) {
                    target[targetOffset + row * targetRowStride + column * targetPixelStride] =
                            scratchRow[column * plane.pixelStride];
                }
            }
        }
    }

    private static final class OptimizedCopier implements Copier {
        private byte[] scratchRow;

        @Override
        public void copy(Plane[] planes, byte[] target) {
            int ySize = WIDTH * HEIGHT;
            int chromaSize = ySize / 4;
            copyPlane(planes[0], WIDTH, HEIGHT, target, 0);
            copyPlane(planes[1], WIDTH / 2, HEIGHT / 2, target, ySize);
            copyPlane(planes[2], WIDTH / 2, HEIGHT / 2, target, ySize + chromaSize);
        }

        private void copyPlane(
                Plane plane,
                int planeWidth,
                int planeHeight,
                byte[] target,
                int targetOffset) {
            byte[] scratch = null;
            if (plane.pixelStride != 1) {
                if (scratchRow == null || scratchRow.length < plane.rowStride) {
                    scratchRow = new byte[plane.rowStride];
                }
                scratch = scratchRow;
            }
            Yuv420PlaneCopier.copy(
                    plane.buffer,
                    plane.rowStride,
                    plane.pixelStride,
                    planeWidth,
                    planeHeight,
                    target,
                    targetOffset,
                    planeWidth,
                    1,
                    scratch);
        }
    }

    private static final class Result {
        final double medianMs;
        final double p95Ms;

        Result(double medianMs, double p95Ms) {
            this.medianMs = medianMs;
            this.p95Ms = p95Ms;
        }
    }

    private Yuv420CopyBenchmark() {}

    public static void main(String[] args) {
        int warmupIterations = parseArgument(args, 0, 50);
        int samples = parseArgument(args, 1, 15);
        int iterationsPerSample = parseArgument(args, 2, 20);

        System.out.printf(
                "runtime=%s vm=%s os_arch=%s resolution=%dx%d warmup=%d samples=%d iterations=%d%n",
                System.getProperty("java.runtime.version"),
                System.getProperty("java.vm.name"),
                System.getProperty("os.arch"),
                WIDTH,
                HEIGHT,
                warmupIterations,
                samples,
                iterationsPerSample);

        runLayout(
                "interleaved-source-to-planar",
                WIDTH,
                2,
                warmupIterations,
                samples,
                iterationsPerSample);
        runLayout(
                "planar-source-to-planar",
                WIDTH / 2,
                1,
                warmupIterations,
                samples,
                iterationsPerSample);
        System.out.println("blackhole=" + blackhole);
    }

    private static void runLayout(
            String name,
            int chromaRowStride,
            int chromaPixelStride,
            int warmupIterations,
            int samples,
            int iterationsPerSample) {
        Plane[] planes = {
                createPlane(WIDTH, HEIGHT, 1, 17),
                createPlane(chromaRowStride, HEIGHT / 2, chromaPixelStride, 31),
                createPlane(chromaRowStride, HEIGHT / 2, chromaPixelStride, 47)
        };
        byte[] legacyTarget = new byte[FRAME_SIZE];
        byte[] optimizedTarget = new byte[FRAME_SIZE];
        Copier legacy = new LegacyCopier();
        Copier optimized = new OptimizedCopier();

        legacy.copy(planes, legacyTarget);
        optimized.copy(planes, optimizedTarget);
        if (!Arrays.equals(legacyTarget, optimizedTarget)) {
            throw new AssertionError("optimized output differs for " + name);
        }

        Result legacyResult = benchmark(
                legacy, planes, legacyTarget, warmupIterations, samples, iterationsPerSample);
        Result optimizedResult = benchmark(
                optimized, planes, optimizedTarget, warmupIterations, samples, iterationsPerSample);
        double medianReduction = reduction(legacyResult.medianMs, optimizedResult.medianMs);
        double p95Reduction = reduction(legacyResult.p95Ms, optimizedResult.p95Ms);

        System.out.printf(
                "layout=%s legacy_median_ms=%.3f optimized_median_ms=%.3f "
                        + "median_reduction_pct=%.1f legacy_p95_ms=%.3f optimized_p95_ms=%.3f "
                        + "p95_reduction_pct=%.1f output_equal=true%n",
                name,
                legacyResult.medianMs,
                optimizedResult.medianMs,
                medianReduction,
                legacyResult.p95Ms,
                optimizedResult.p95Ms,
                p95Reduction);
    }

    private static Result benchmark(
            Copier copier,
            Plane[] planes,
            byte[] target,
            int warmupIterations,
            int samples,
            int iterationsPerSample) {
        long checksum = 0;
        for (int iteration = 0; iteration < warmupIterations; iteration++) {
            copier.copy(planes, target);
            checksum += target[(iteration * 997) % target.length] & 0xff;
        }

        double[] sampleMs = new double[samples];
        for (int sample = 0; sample < samples; sample++) {
            long startedAtNs = System.nanoTime();
            for (int iteration = 0; iteration < iterationsPerSample; iteration++) {
                copier.copy(planes, target);
                checksum += target[((sample * iterationsPerSample + iteration) * 997)
                        % target.length] & 0xff;
            }
            sampleMs[sample] = (System.nanoTime() - startedAtNs)
                    / 1_000_000.0
                    / iterationsPerSample;
        }
        blackhole += checksum;
        Arrays.sort(sampleMs);
        return new Result(percentile(sampleMs, 0.50), percentile(sampleMs, 0.95));
    }

    private static Plane createPlane(int rowStride, int height, int pixelStride, int seed) {
        byte[] data = new byte[rowStride * height];
        for (int index = 0; index < data.length; index++) {
            data[index] = (byte) (seed + index * 13);
        }
        return new Plane(ByteBuffer.wrap(data), rowStride, pixelStride);
    }

    private static int parseArgument(String[] args, int index, int defaultValue) {
        if (args.length <= index) return defaultValue;
        int value = Integer.parseInt(args[index]);
        if (value <= 0) throw new IllegalArgumentException("benchmark arguments must be positive");
        return value;
    }

    private static double percentile(double[] sorted, double percentile) {
        int index = (int) Math.ceil(percentile * sorted.length) - 1;
        return sorted[Math.max(0, Math.min(index, sorted.length - 1))];
    }

    private static double reduction(double before, double after) {
        return (before - after) / before * 100.0;
    }
}
