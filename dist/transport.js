import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { Agent, request } from 'node:http';
export async function postJsonVerified(url, token, body, signal) {
    const target = new URL(url);
    const agent = new Agent({ keepAlive: true, maxSockets: 1 });
    return await new Promise((resolve, reject) => {
        let active;
        let finished = false;
        const finish = (error, response) => {
            if (finished)
                return;
            finished = true;
            signal.removeEventListener('abort', abort);
            active?.destroy();
            agent.destroy();
            if (error)
                reject(error);
            else
                resolve(response);
        };
        const abort = () => finish(new Error('Local System One request timed out'));
        if (signal.aborted) {
            abort();
            return;
        }
        signal.addEventListener('abort', abort, { once: true });
        const nonce = randomBytes(16).toString('hex');
        let pinned = null;
        const collect = (response, limit, done) => {
            let data = '';
            response.setEncoding('utf8');
            response.on('data', (chunk) => {
                data += chunk;
                if (Buffer.byteLength(data) > limit)
                    finish(new Error('Local System One response is too large'));
            });
            response.on('error', error => finish(error));
            response.on('end', () => { if (!finished)
                done(data); });
        };
        active = request({ hostname: target.hostname, port: target.port || 80, method: 'GET',
            path: '/_local_system_one/identity', agent,
            headers: { 'X-Local-System-One-Challenge': nonce } }, response => {
            pinned = response.socket;
            collect(response, 1024, data => {
                if (response.statusCode !== 200) {
                    finish(undefined, new Response(null, { status: response.statusCode || 503 }));
                    return;
                }
                let proof;
                try {
                    proof = JSON.parse(data).proof;
                }
                catch {
                    finish(new Error('Local System One identity is unverified'));
                    return;
                }
                const expected = createHmac('sha256', token).update(`identity:${nonce}:${pinned?.remoteAddress}:${pinned?.remotePort}`).digest('hex');
                if (typeof proof !== 'string' || !/^[0-9a-f]{64}$/.test(proof)
                    || !timingSafeEqual(Buffer.from(proof, 'hex'), Buffer.from(expected, 'hex')) || !pinned) {
                    finish(new Error('Local System One identity is unverified'));
                    return;
                }
                active = request({ hostname: target.hostname, port: target.port || 80, method: 'POST',
                    path: target.pathname, agent, headers: { 'content-type': 'application/json',
                        authorization: `Bearer ${token}`, 'content-length': Buffer.byteLength(body) } }, result => {
                    collect(result, 1_048_576, data => finish(undefined, new Response(data, { status: result.statusCode || 503 })));
                });
                active.on('error', error => finish(error));
                active.on('socket', socket => {
                    if (socket !== pinned) {
                        finish(new Error('Verified Runtime connection was closed'));
                        return;
                    }
                    active?.end(body);
                });
            });
        });
        active.on('error', error => finish(error));
        active.end();
    });
}
//# sourceMappingURL=transport.js.map