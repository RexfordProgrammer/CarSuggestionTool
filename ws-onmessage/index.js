import { DeleteCommand, GetCommand } from "@aws-sdk/lib-dynamodb";
import { ddbDoc, TABLE } from "../utils/db.js";

export const handler = async (event) => {
  const connectionId = event.requestContext.connectionId;

  // (Optional) read to log who disconnected
  await ddbDoc.send(new GetCommand({
    TableName: TABLE, Key: { pk: "CONN", sk: connectionId }
  })).catch(() => null);

  await ddbDoc.send(new DeleteCommand({
    TableName: TABLE,
    Key: { pk: "CONN", sk: connectionId }
  }));

  return { statusCode: 200, body: "bye" };
};
