/* Execute in the logged-in cbastats page. client is its observed authenticated
   application client; never extract cookies/tokens. Imports/hashes are discovered
   from the current public page and are not permanent API credentials. */
export async function playerGames(client, playerId, year, stageType) {
 return (await client.post('/api/base/shoot-plot/games', [{leagueIds:[10003],seasonYears:[year],stageTypes:[stageType],playerId:String(playerId)}])).data;
}
export async function teamGames(client, teamIds, year, stageType) {
 const rows=(await client.post('/api/base/shoot-plot/games',teamIds.map(teamId=>({leagueIds:[10003],seasonYears:[year],stageTypes:[stageType],playerId:null,teamId})))).data;
 return [...new Map(rows.map(r=>[r.scheduleId,r])).values()];
}
export async function coordinates(client, scheduleIds, playerId) {
 const body={scheduleIds};if(playerId!==undefined)body.playerId=String(playerId);
 return (await client.post('/api/player-shot/shot-plot',body)).data;
}
export async function playerTotals(client,playerId,year,seasonId,stageType) {
 return (await client.post('/api/players/match-base-data-info/player',{playerId,leagueIds:[10003],seasonId,seasonYears:[year],stageType,stageTypes:[stageType],dataType:'sum'})).data;
}
// Fetch/cache each whole game, not a player-filtered excerpt, for cross-player reuse.
export async function fullGameEvents(pbpFunction,scheduleId) {
 let start=0,records=[],seen=new Set();
 for(let page=0;page<100;page++) {
  const data=(await pbpFunction({scheduleId},start)).data;
  const next=(data.records||[]).filter(r=>!seen.has(r.id));
  if(!next.length)break;
  next.forEach(r=>seen.add(r.id));records.push(...next);start+=data.records.length;
  if((data.total!==undefined&&records.length>=data.total)||data.hasNext===false)break;
  if(page===99)throw Error('PbP pagination did not terminate');
 }
 return {scheduleId,scope:'whole-game',records};
}
