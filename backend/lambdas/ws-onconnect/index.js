import { PutCommand } from "@aws-sdk/lib-dynamodb";
import { ddbDoc, TABLE } from "../utils/db.js";

// If you’re using an authorizer, you’ll get claims in event.requestContext.authorizer (e.g., sub/email)
export const handler = async (event) => {
  const connectionId = event.requestContext.connectionId;

  // Optional: derive a session per user; for demo, generate one here
  const userSub = event.requestContext.authorizer?.sub || "anonymous";
  const sessionId = `s#${userSub}`;

  const ttl = Math.floor(Date.now() / 1000) + 60 * 60 * 24; // 24h

  await ddbDoc.send(new PutCommand({
    TableName: TABLE,
    Item: {
      pk: "CONN", sk: connectionId,
      userSub, sessionId, ttl,
      connectedAt: new Date().toISOString()
    }
  }));

  // Optionally seed session
  await ddbDoc.send(new PutCommand({
    TableName: TABLE,
    Item: {
      pk: "SESSION", sk: sessionId,
      userSub, ruledIn: [], ruledOut: [], history: [], updatedAt: new Date().toISOString()
    },
    // Don’t overwrite if it exists
    ConditionExpression: "attribute_not_exists(pk)"
  })).catch(() => { /* ignore if already exists */ });

  return { statusCode: 200, body: "ok" };
};
