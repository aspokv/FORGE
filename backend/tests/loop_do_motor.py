"""Um unico event loop para os testes que falam com o Motor dentro do processo.

O cliente do Motor se prende ao loop onde foi tocado pela primeira vez. Dois arquivos com
loops proprios passam quando rodam sozinhos e quebram quando rodam juntos, com um erro que
nao aponta para a causa ("attached to a different loop") e que depende da ordem de coleta
do pytest. Um loop so, importado pelos dois, tira a ordem de execucao da equacao.

Os demais arquivos de teste falam com um servidor HTTP de verdade e nao compartilham este
cliente, entao continuam com seus proprios loops sem conflito.
"""
import asyncio

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
