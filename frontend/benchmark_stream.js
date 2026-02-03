
import { Readable } from 'stream';

async function runBenchmarks() {
    // 1000 chunks of "event: message\ndata: \"a\"\n\n"
    const createReader = () => {
        const chunks = [];
        for (let i = 0; i < 1000; i++) {
            chunks.push(new TextEncoder().encode(`event: message\ndata: "a"\n\n`));
        }
        const stream = new Readable({
            read() {
                this.push(chunks.length ? chunks.shift() : null);
            }
        });
        return {
            async read() {
                const chunk = stream.read();
                return { done: chunk === null, value: chunk };
            }
        };
    };

    console.log("Running Baseline...");
    await runBenchmark("Baseline", currentImplementation, createReader());

    console.log("\nRunning Optimized...");
    await runBenchmark("Optimized", optimizedImplementation, createReader());
}

async function runBenchmark(name, implementation, reader) {
    let updateCount = 0;
    const setMessages = () => { updateCount++; };

    const start = Date.now();
    await implementation(reader, setMessages);
    const end = Date.now();

    console.log(`[${name}] Updates: ${updateCount}, Time: ${end - start}ms`);
}

// Current Implementation
async function currentImplementation(reader, setMessages) {
    let currentText = "";
    let buffer = "";
    const decoder = new TextDecoder("utf-8");

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || "";

        for (const part of parts) {
            if (!part.trim()) continue;
            const lines = part.split('\n');
            let eventType = "";
            let data = "";

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    data = line.slice(6);
                }
            }

            if (eventType === 'message' || (!eventType && data)) {
                 if (data) {
                    try {
                        const parsedText = JSON.parse(data);
                        currentText += parsedText;
                        setMessages(); // Mocking the state update
                    } catch (e) {}
                 }
            }
        }
    }
}

// Optimized Implementation (Proposed)
async function optimizedImplementation(reader, setMessages) {
    let currentText = "";
    let buffer = "";
    const decoder = new TextDecoder("utf-8");
    let lastUpdate = 0;
    const THROTTLE_MS = 16; // ~60fps

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
             // Final update to ensure we didn't miss anything
             setMessages();
             break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || "";

        let hasNewText = false;

        for (const part of parts) {
            if (!part.trim()) continue;
            const lines = part.split('\n');
            let eventType = "";
            let data = "";

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    data = line.slice(6);
                }
            }

            if (eventType === 'message' || (!eventType && data)) {
                 if (data) {
                    try {
                        const parsedText = JSON.parse(data);
                        currentText += parsedText;
                        hasNewText = true;
                    } catch (e) {}
                 }
            }
        }

        if (hasNewText) {
            const now = Date.now();
            if (now - lastUpdate > THROTTLE_MS) {
                setMessages();
                lastUpdate = now;
            }
        }
    }
}

runBenchmarks();
