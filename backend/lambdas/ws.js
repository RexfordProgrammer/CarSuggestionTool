import { ApiGatewayManagementApiClient, PostToConnectionCommand } from "@aws-sdk/client-apigatewaymanagementapi";

export const wsClientFor = (event) => {
  // Build the WS management endpoint from the request context
  const { domainName, stage } = event.requestContext;
  const endpoint = `https://${domainName}/${stage}`;
  return new ApiGatewayManagementApiClient({ endpoint });
};

export const postJson = async (client, connectionId, payload) => {
  const data = Buffer.from(JSON.stringify(payload));
  await client.send(new PostToConnectionCommand({
    ConnectionId: connectionId,
    Data: data
  }));
};
